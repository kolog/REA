package rea;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.PrintWriter;
import java.lang.instrument.Instrumentation;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collection;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentLinkedQueue;

/**
 * REA agent: attaches to PokeWilds (-javaagent), exposes a frame-synchronous
 * control socket on 127.0.0.1 (JSON lines). Everything touching game objects
 * runs on the render thread via Gdx.app.postRunnable, so state reads are race-free
 * and inputs land exactly at the start of a frame.
 *
 * Commands (one per line):
 *   ping
 *   state                       -> snapshot at next frame boundary
 *   do <keys|-> <frames>        -> hold keys (a+b+up+...) for N frames, then snapshot
 *   grid <radius>               -> tiles around the player
 *   get <path> [depth]          -> reflective inspect, path like "player.pokemon.0"
 *   type <text>                 -> feed characters to the active text field
 *   release                     -> give keyboard control back to the human
 */
public final class Agent {
    static final String[] KEYS = {"up", "down", "left", "right", "a", "b", "start", "l", "r"};

    static Class<?> gdx, game, input;
    static Object app;
    static volatile PrintWriter out;
    static final ConcurrentLinkedQueue<String> inbox = new ConcurrentLinkedQueue<>();

    // render-thread state
    static boolean[] held = new boolean[KEYS.length];
    static boolean[] want = new boolean[KEYS.length];
    static int remaining = 0;
    static boolean replyWhenDone = false;
    static boolean controlling = false;

    public static void premain(String args, Instrumentation inst) { start(args); }
    public static void agentmain(String args, Instrumentation inst) { start(args); }

    static void start(String args) {
        final int port = args != null && args.matches("\\d+") ? Integer.parseInt(args) : 7777;
        Thread t = new Thread(() -> boot(port), "rea-boot");
        t.setDaemon(true);
        t.start();
    }

    static void boot(int port) {
        try {
            // wait for the game to be up
            while (true) {
                try {
                    gdx = Class.forName("com.badlogic.gdx.Gdx");
                    game = Class.forName("com.pkmngen.game.Game");
                    input = Class.forName("com.pkmngen.game.InputProcessor");
                    app = gdx.getField("app").get(null);
                    if (app != null && sget(game, "staticGame") != null) break;
                } catch (Throwable ignored) { }
                Thread.sleep(250);
            }
            log("game detected, serving on 127.0.0.1:" + port);
            post(Agent::tick);
            ServerSocket ss = new ServerSocket(port, 1, InetAddress.getByName("127.0.0.1"));
            while (true) {
                Socket s = ss.accept();
                s.setTcpNoDelay(true);
                serve(s);
            }
        } catch (Throwable e) {
            log("fatal: " + e);
        }
    }

    static void serve(Socket s) {
        try (BufferedReader in = new BufferedReader(new InputStreamReader(s.getInputStream(), StandardCharsets.UTF_8));
             PrintWriter w = new PrintWriter(s.getOutputStream(), true, StandardCharsets.UTF_8)) {
            out = w;
            String line;
            while ((line = in.readLine()) != null) inbox.add(line.trim());
        } catch (IOException ignored) {
        } finally {
            out = null;
            inbox.add("release");
        }
    }

    static void post(Runnable r) {
        try {
            app.getClass().getMethod("postRunnable", Runnable.class).invoke(app, r);
        } catch (Throwable e) { log("post failed: " + e); }
    }

    static void log(String m) { System.out.println("[REA] " + m); }

    // ---------------------------------------------------------------- render-thread tick
    static void tick() {
        try {
            if (replyWhenDone && remaining == 0) {
                replyWhenDone = false;
                send(snapshot());
            }
            while (remaining == 0 && !replyWhenDone && !inbox.isEmpty()) handle(inbox.poll());
            applyInput();
        } catch (Throwable e) {
            send("{\"error\":" + q(e.toString()) + "}");
        } finally {
            post(Agent::tick); // run again next frame, before render()
        }
    }

    static void applyInput() throws Exception {
        if (!controlling) return;
        boolean[] cur = remaining > 0 ? want : new boolean[KEYS.length];
        for (int i = 0; i < KEYS.length; i++) {
            boolean just = cur[i] && !held[i];
            held[i] = cur[i];
            sset(input, KEYS[i] + "Pressed", cur[i]);
            sset(input, KEYS[i] + "JustPressed", just);
        }
        if (remaining > 0) { remaining--; if (remaining == 0) replyWhenDone = true; }
    }

    static void takeControl(boolean on) throws Exception {
        controlling = on;
        sset(input, "acceptInput", !on);
        if (!on) held = new boolean[KEYS.length];
    }

    static void handle(String line) throws Exception {
        if (line == null || line.isEmpty()) return;
        String[] p = line.split("\\s+");
        switch (p[0]) {
            case "ping": send("{\"ok\":true,\"frame\":" + frame() + "}"); break;
            case "state": send(snapshot()); break;
            case "release": takeControl(false); break;
            case "do": {
                takeControl(true);
                want = new boolean[KEYS.length];
                if (!p[1].equals("-")) for (String k : p[1].split("\\+")) {
                    int i = java.util.Arrays.asList(KEYS).indexOf(k);
                    if (i < 0) { send("{\"error\":\"bad key " + k + "\"}"); return; }
                    want[i] = true;
                }
                remaining = Math.max(1, Integer.parseInt(p[2]));
                break;
            }
            case "type": { // feed characters to the game's text-field input processor
                Object ip = gdx.getField("input").get(null);
                Object proc = ip.getClass().getMethod("getInputProcessor").invoke(ip);
                String txt = line.substring(5);
                Method kt = Class.forName("com.badlogic.gdx.InputProcessor").getMethod("keyTyped", char.class);
                if (proc != null)
                    for (char c : txt.toCharArray()) kt.invoke(proc, c);
                send("{\"typed\":" + (proc != null) + "}");
                break;
            }
            case "grid": send(grid(p.length > 1 ? Integer.parseInt(p[1]) : 8)); break;
            case "get": send(inspect(p[1], p.length > 2 ? Integer.parseInt(p[2]) : 2)); break;
            default: send("{\"error\":\"unknown command\"}");
        }
    }

    static void send(String json) {
        PrintWriter w = out;
        if (w != null) w.println(json);
    }

    // ---------------------------------------------------------------- snapshot
    static long frame() throws Exception {
        Object g = gdx.getField("graphics").get(null);
        return (Long) g.getClass().getMethod("getFrameId").invoke(g);
    }

    static Object G() { return sget(game, "staticGame"); }

    static String snapshot() throws Exception {
        Object g = G();
        StringBuilder sb = new StringBuilder("{\"frame\":").append(frame());
        // action stack: tells the bot which screen/menu is active
        sb.append(",\"actions\":[");
        List<?> acts = (List<?>) fget(g, "actionStack");
        boolean first = true;
        for (Object a : new ArrayList<>(acts)) {
            if (a == null) continue;
            String n = a.getClass().getName();
            n = n.substring(n.lastIndexOf('.') + 1);
            sb.append(first ? "" : ",").append(q(n));
            first = false;
        }
        sb.append("]");
        sb.append(",\"playerCanMove\":").append(fget(g, "playerCanMove"));
        Object pl = fget(g, "player");
        if (pl != null) sb.append(",\"player\":").append(player(pl));
        Object map = fget(g, "map");
        if (map != null) sb.append(",\"map\":").append(map(map));
        Object battle = fget(g, "battle");
        if (battle != null) {
            sb.append(",\"battle\":{\"turn\":").append(fget(battle, "turnNumber"));
            Object opp = fget(battle, "oppPokemon");
            if (opp != null) sb.append(",\"opp\":").append(pokemon(opp));
            sb.append(",\"weather\":").append(q(str(fget(battle, "weather"))));
            sb.append("}");
        }
        return sb.append("}").toString();
    }

    static String player(Object pl) throws Exception {
        Object pos = fget(pl, "position");
        StringBuilder sb = new StringBuilder("{");
        sb.append("\"x\":").append(fget(pos, "x")).append(",\"y\":").append(fget(pos, "y"));
        sb.append(",\"dir\":").append(q(str(fget(pl, "dirFacing"))));
        sb.append(",\"name\":").append(q(str(fget(pl, "name"))));
        sb.append(",\"state\":").append(q(str(fget(pl, "currState"))));
        sb.append(",\"canMove\":").append(fget(pl, "canMove"));
        sb.append(",\"isSleeping\":").append(fget(pl, "isSleeping"));
        sb.append(",\"isFishing\":").append(fget(pl, "isFishing"));
        sb.append(",\"adrenaline\":").append(fget(pl, "adrenaline"));
        sb.append(",\"items\":").append(mapJson(fget(pl, "itemsDict")));
        sb.append(",\"party\":[");
        List<?> party = (List<?>) fget(pl, "pokemon");
        for (int i = 0; party != null && i < party.size(); i++)
            sb.append(i > 0 ? "," : "").append(pokemon(party.get(i)));
        sb.append("],\"curr\":").append(party != null ? party.indexOf(fget(pl, "currPokemon")) : -1);
        return sb.append("}").toString();
    }

    static String pokemon(Object pk) throws Exception {
        if (pk == null) return "null";
        Object sp = fget(pk, "specie");
        StringBuilder sb = new StringBuilder("{");
        sb.append("\"specie\":").append(q(str(sp == null ? null : fget(sp, "name"))));
        sb.append(",\"nick\":").append(q(str(fget(pk, "nickname"))));
        sb.append(",\"lvl\":").append(fget(pk, "level")).append(",\"exp\":").append(fget(pk, "exp"));
        sb.append(",\"happy\":").append(fget(pk, "happiness"));
        sb.append(",\"status\":").append(q(str(fget(pk, "status"))));
        sb.append(",\"types\":").append(listJson(fget(pk, "types")));
        sb.append(",\"stats\":").append(mapJson(fget(pk, "currentStats")));
        sb.append(",\"max\":").append(mapJson(fget(pk, "maxStats")));
        sb.append(",\"stages\":").append(mapJson(fget(pk, "statStages")));
        Object atk = fget(pk, "attacks");
        sb.append(",\"moves\":[");
        if (atk instanceof Object[]) {
            Object[] a = (Object[]) atk;
            for (int i = 0; i < a.length; i++) sb.append(i > 0 ? "," : "").append(q(str(a[i])));
        }
        return sb.append("],\"pp\":").append(arrJson(fget(pk, "currentPP"))).append(",\"x\":")
                .append(posOf(pk)).append("}").toString();
    }

    static String posOf(Object pk) {
        try {
            Object pos = fget(pk, "position");
            return pos == null ? "null" : "[" + fget(pos, "x") + "," + fget(pos, "y") + "]";
        } catch (Throwable t) { return "null"; }
    }

    static String map(Object map) throws Exception {
        StringBuilder sb = new StringBuilder("{");
        sb.append("\"id\":").append(q(str(fget(map, "currMapId"))));
        sb.append(",\"biome\":").append(q(str(fget(map, "currBiome"))));
        sb.append(",\"time\":").append(q(str(fget(map, "timeOfDay"))));
        sb.append(",\"interior\":").append(fget(map, "tiles") != fget(map, "overworldTiles"));
        Object route = fget(map, "currRoute");
        if (route != null)
            sb.append(",\"route\":").append(q(str(fget(route, "name")))).append(",\"routeLevel\":").append(fget(route, "level"));
        sb.append(",\"mons\":[");
        List<?> mons = (List<?>) fget(map, "onscreenPokemon");
        boolean first = true;
        for (Object m : new ArrayList<>(mons)) {
            sb.append(first ? "" : ",").append(pokemon(m));
            first = false;
        }
        return sb.append("]}").toString();
    }

    static String grid(int r) throws Exception {
        Object map = fget(G(), "map");
        Object pl = fget(G(), "player");
        Object pos = fget(pl, "position");
        float px = (Float) fget(pos, "x"), py = (Float) fget(pos, "y");
        Map<?, ?> tiles = (Map<?, ?>) fget(map, "tiles");
        Class<?> v2 = Class.forName("com.badlogic.gdx.math.Vector2");
        Object key = v2.getConstructor(float.class, float.class).newInstance(0f, 0f);
        Method set = v2.getMethod("set", float.class, float.class);
        StringBuilder sb = new StringBuilder("{\"px\":").append(px).append(",\"py\":").append(py)
                .append(",\"r\":").append(r).append(",\"tiles\":[");
        boolean first = true;
        for (int dy = r; dy >= -r; dy--) {
            for (int dx = -r; dx <= r; dx++) {
                set.invoke(key, px + dx * 16f, py + dy * 16f);
                Object t = tiles.get(key);
                if (!first) sb.append(',');
                first = false;
                if (t == null) { sb.append("null"); continue; }
                sb.append("{\"n\":").append(q(str(fget(t, "name")))).append(",\"u\":").append(q(str(fget(t, "nameUpper"))));
                for (String f : new String[]{"isSolid", "isLedge", "isWater", "isGrass", "isTree", "isSmashable",
                        "isCuttable", "isHeadbuttable", "isLava", "isWaterfall"})
                    if (Boolean.TRUE.equals(fget(t, f))) sb.append(",\"").append(f.substring(2).toLowerCase()).append("\":1");
                String led = str(fget(t, "ledgeDir"));
                if (!led.isEmpty()) sb.append(",\"ledge\":").append(q(led));
                String it = str(fget(t, "hasItem"));
                if (!it.isEmpty()) sb.append(",\"item\":").append(q(it));
                sb.append("}");
            }
        }
        return sb.append("]}").toString();
    }

    // ---------------------------------------------------------------- reflective inspector
    static String inspect(String path, int depth) throws Exception {
        Object cur;
        String[] parts;
        if (path.startsWith("class:") && path.contains("#")) { // class:com.x.Y#field.sub
            String[] rest = path.substring(path.indexOf('#') + 1).split("\\.");
            parts = new String[rest.length + 1];
            parts[0] = path.substring(0, path.indexOf('#'));
            System.arraycopy(rest, 0, parts, 1, rest.length);
        } else parts = path.split("\\.");
        int i = 0;
        if (parts[0].equals("game")) { cur = G(); i = 1; }
        else if (parts[0].startsWith("class:")) { cur = Class.forName(parts[0].substring(6)); i = 1; }
        else cur = G();
        for (; i < parts.length && cur != null; i++) {
            String s = parts[i];
            if (cur instanceof List && s.matches("\\d+")) cur = ((List<?>) cur).get(Integer.parseInt(s));
            else if (cur instanceof Map) cur = ((Map<?, ?>) cur).get(s);
            else if (cur instanceof Class) cur = sget((Class<?>) cur, s);
            else cur = fget(cur, s);
        }
        return "{\"value\":" + dump(cur, depth) + "}";
    }

    static String[] concat(String first, String[] rest) {
        String[] r = new String[rest.length + 1];
        r[0] = first;
        System.arraycopy(rest, 0, r, 1, rest.length);
        return r;
    }

    static String dump(Object o, int depth) throws Exception {
        if (o == null) return "null";
        if (o instanceof Number || o instanceof Boolean) return o.toString();
        if (o instanceof CharSequence || o instanceof Enum || o instanceof Character) return q(o.toString());
        if (depth <= 0) return q(o.getClass().getSimpleName() + "@");
        if (o instanceof Map) {
            StringBuilder sb = new StringBuilder("{");
            int n = 0;
            for (Map.Entry<?, ?> e : ((Map<?, ?>) o).entrySet()) {
                if (n++ >= 200) break;
                sb.append(n > 1 ? "," : "").append(q(String.valueOf(e.getKey()))).append(':').append(dump(e.getValue(), depth - 1));
            }
            return sb.append("}").toString();
        }
        if (o instanceof Collection || o instanceof Object[]) {
            Collection<?> c = o instanceof Collection ? (Collection<?>) o : java.util.Arrays.asList((Object[]) o);
            StringBuilder sb = new StringBuilder("[");
            int n = 0;
            for (Object e : c) {
                if (n++ >= 200) break;
                sb.append(n > 1 ? "," : "").append(dump(e, depth - 1));
            }
            return sb.append("]").toString();
        }
        if (o.getClass().isArray()) return arrJson(o);
        StringBuilder sb = new StringBuilder("{\"@\":").append(q(o.getClass().getName()));
        for (Class<?> c = o.getClass(); c != null && c != Object.class; c = c.getSuperclass()) {
            for (Field f : c.getDeclaredFields()) {
                if (java.lang.reflect.Modifier.isStatic(f.getModifiers())) continue;
                f.setAccessible(true);
                Object v;
                try { v = f.get(o); } catch (Throwable t) { continue; }
                String cn = f.getType().getName();
                if (cn.contains("Texture") || cn.contains("Sprite") || cn.contains("Batch") || cn.contains("Music")) continue;
                sb.append(',').append(q(f.getName())).append(':').append(dump(v, depth - 1));
            }
        }
        return sb.append("}").toString();
    }

    // ---------------------------------------------------------------- reflection + json helpers
    static Object fget(Object o, String name) {
        for (Class<?> c = o.getClass(); c != null; c = c.getSuperclass()) {
            try {
                Field f = c.getDeclaredField(name);
                f.setAccessible(true);
                return f.get(o);
            } catch (NoSuchFieldException e) { /* climb */ } catch (Throwable e) { return null; }
        }
        return null;
    }

    static Object sget(Class<?> c, String name) {
        try {
            Field f = c.getDeclaredField(name);
            f.setAccessible(true);
            return f.get(null);
        } catch (Throwable e) { return null; }
    }

    static void sset(Class<?> c, String name, Object v) throws Exception {
        Field f = c.getDeclaredField(name);
        f.setAccessible(true);
        f.set(null, v);
    }

    static String str(Object o) { return o == null ? "" : o.toString(); }

    static String q(String s) {
        StringBuilder sb = new StringBuilder("\"");
        for (char c : s.toCharArray()) {
            if (c == '"' || c == '\\') sb.append('\\').append(c);
            else if (c < 0x20) sb.append(String.format("\\u%04x", (int) c));
            else sb.append(c);
        }
        return sb.append('"').toString();
    }

    static String mapJson(Object m) {
        if (!(m instanceof Map)) return "{}";
        StringBuilder sb = new StringBuilder("{");
        boolean first = true;
        for (Map.Entry<?, ?> e : ((Map<?, ?>) m).entrySet()) {
            sb.append(first ? "" : ",").append(q(String.valueOf(e.getKey()))).append(':').append(e.getValue());
            first = false;
        }
        return sb.append("}").toString();
    }

    static String listJson(Object l) {
        if (!(l instanceof Collection)) return "[]";
        StringBuilder sb = new StringBuilder("[");
        boolean first = true;
        for (Object e : (Collection<?>) l) {
            sb.append(first ? "" : ",").append(q(String.valueOf(e)));
            first = false;
        }
        return sb.append("]").toString();
    }

    static String arrJson(Object a) {
        if (a == null || !a.getClass().isArray()) return "[]";
        StringBuilder sb = new StringBuilder("[");
        int n = java.lang.reflect.Array.getLength(a);
        for (int i = 0; i < n; i++) sb.append(i > 0 ? "," : "").append(java.lang.reflect.Array.get(a, i));
        return sb.append("]").toString();
    }
}
