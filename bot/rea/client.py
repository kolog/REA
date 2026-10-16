"""Frame-synchronous client for the REA Java agent (see agent/src/rea/Agent.java)."""
import json
import socket
import time

KEYS = ("up", "down", "left", "right", "a", "b", "start", "l", "r")


class Conn:
    def __init__(self, host="127.0.0.1", port=7777, timeout=15.0):
        deadline = time.time() + timeout
        while True:
            try:
                self.sock = socket.create_connection((host, port), timeout=2)
                break
            except OSError:
                if time.time() > deadline:
                    raise
                time.sleep(0.5)
        self.sock.settimeout(30)
        self.f = self.sock.makefile("rw", encoding="utf-8", newline="\n")

    def call(self, line):
        self.f.write(line + "\n")
        self.f.flush()
        resp = self.f.readline()
        if not resp:
            raise ConnectionError("agent closed the connection")
        data = json.loads(resp)
        if isinstance(data, dict) and "error" in data:
            raise RuntimeError(data["error"])
        return data

    def close(self):
        try:
            self.f.write("release\n")
            self.f.flush()
        finally:
            self.sock.close()


class Game(Conn):
    """High level helpers. Every call that advances time returns the new state."""

    def state(self):
        return self.call("state")

    def hold(self, keys, frames=1):
        if isinstance(keys, str):
            keys = [keys]
        return self.call("do %s %d" % ("+".join(keys) or "-", frames))

    def wait(self, frames=1):
        return self.call("do - %d" % frames)

    def tap(self, key, hold=2, gap=4):
        """Press a button for `hold` frames then release for `gap` frames."""
        self.hold(key, hold)
        return self.wait(gap)

    def walk(self, dirs):
        """Follow a list of directions. Returns (state, result, steps_done)."""
        s = self.call("walk " + ",".join(dirs))
        w = s.get("walk", {})
        return s, w.get("result"), w.get("done", 0)

    def grid(self, r=8):
        return self.call("grid %d" % r)

    def get(self, path, depth=2):
        return self.call("get %s %d" % (path, depth))["value"]

    def act(self, name, depth=1):
        """Fields of the first action on the stack with this class name (None if absent)."""
        return self.call("act %s %d" % (name, depth))["value"]

    def save(self):
        """Write the current world to its .sav file right now."""
        return self.call("save")

    def world(self):
        return self.call("world")

    def objects(self):
        return self.call("objects")["objs"]

    def allmons(self):
        """[(specie, level, temper, tx, ty, holds)] for every overworld pokemon in the world."""
        return [tuple(m) for m in self.call("allmons")["mons"]]
