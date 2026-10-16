# REA — bot autônomo para PokeWilds (v0.8.11, offline)

Arquitetura (sem visão computacional, sem simular teclado):

```
PokeWilds (JVM) ── rea-agent.jar (-javaagent) ── TCP 127.0.0.1:7777 ── bot/ (Python)
```

* **agent/** — agente Java. Roda dentro do jogo, lê o estado por reflexão e injeta os botões
  (`InputProcessor.*Pressed`) *quadro a quadro* na thread de render. Determinístico, não precisa de foco de janela.
* **bot/rea/** — cliente Python (`Game.hold`, `tap`, `state`, `grid`, `get`).
* **tools/launch_game.ps1** — abre o jogo com o agente.

## Uso
```
bash agent/build.sh                 # precisa de JDK 17
powershell tools/launch_game.ps1    # abre o jogo
python bot/smoke_test.py            # conecta, lê estado e anda
```

Protocolo (uma linha por comando): `ping`, `state`, `do <up+a|-> <frames>`, `grid <r>`, `get <caminho> [prof]`,
`type <texto>`, `release`. `get class:com.pkmngen.game.X#campo` lê estáticos.

## Roadmap
- [x] M0 — ponte agente↔Python, estado, input, menu inicial, novo jogo
- [x] M1 — navegação: grid de tiles, A* em trechos curtos, caminhada contínua no agente, exploração
- [ ] M2 — batalha (tabela de tipos, escolha de golpe, captura, fuga)
- [ ] M3 — sobrevivência/crafting (itens, receitas, fogueira, construção, dormir)
- [ ] M4 — progressão (time, evolução, ginásios/lendários, objetivo final)
