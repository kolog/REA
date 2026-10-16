# REA — bot autônomo para PokeWilds (v0.8.11, offline)

Arquitetura (sem visão computacional, sem simular teclado):

```
PokeWilds (JVM) ── rea-agent.jar (-javaagent) ── TCP 127.0.0.1:7777 ── bot/ (Python)
```

* **agent/** — agente Java. Roda dentro do jogo, lê o estado por reflexão e injeta os botões
  (`InputProcessor.*Pressed`) *quadro a quadro* na thread de render. Determinístico, não precisa de foco de janela.
* **bot/rea/** — cliente Python (`Game.hold`, `tap`, `state`, `grid`, `get`).
* **tools/launch_game.ps1** — abre o jogo com o agente.

## Jogar (resumo)
`powershell -File tools/play.ps1 -Mission auto -Seconds 100` (abre o jogo com o agente, carrega `default.sav` e joga).
Missões: `auto`, `train`, `balls`, `flyer`. Rode em primeiro plano, em rodadas de ~100 s. Skill: `docs/skill/SKILL.md`
(instalada em `~/.claude/skills/pokewilds-bot`).

## Uso
```
bash agent/build.sh                 # precisa de JDK 17
powershell tools/launch_game.ps1    # abre o jogo
python bot/smoke_test.py            # conecta, lê estado e anda
```

Protocolo (uma linha por comando): `ping`, `state`, `do <up+a|-> <frames>`, `grid <r>`, `get <caminho> [prof]`,
`type <texto>`, `release`. `get class:com.pkmngen.game.X#campo` lê estáticos.

## Módulos (bot/rea)
`client` ponte TCP · `nav`/`world`/`travel` mapa e caminhos · `battle` luta/troca/captura (bola escolhida pelas regras do jogo) ·
`rest` dormir no saco · `field` golpes de campo e menu de Pokémon · `economy` coleta, construção, fogueira, crafting ·
`recruit` recrutar Pokémon e pegar itens · `farm` fazenda (soltar em habitat, colher, trazer de volta) · `base` abrigo
(3 telhados + 2 cercas = produção em dobro) · `trainer` treino em zona de grama · `brain` orquestrador de prioridades.
Mecânicas descobertas na engenharia reversa: `docs/MECHANICS.md`.

## Roadmap
- [x] M0 ponte · M1 navegação · M2 batalha/descanso/save-load
- [x] M3 recrutar, coletar, construir, fabricar, capturar, fazenda e base
- [x] M4 casa 5x3 (sono em casa), cercadinhos com portão, fazenda (fogo/água/elétrico), bolas, treino do líder, fantasmas
- [ ] M5 mobiliar a casa (baú/cama), Xatu->FLY e viagem aérea, SURF, Meganium (árvores grandes), mansão/chave, fósseis e pedras
