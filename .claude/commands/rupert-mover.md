Interprete o comando de movimento em linguagem natural e execute no Rupert via MCP rupert.

Regras:
- Use mover_servo para mover um servo específico
- Use mover_sequencia para mover múltiplos servos de uma vez
- Use mover_para_posicao para posições nomeadas (home, pronto, descanso, pegar, soltar)
- Use executar_gesto para sequências animadas (acenar, pegar_objeto, demonstracao)
- Confirme o resultado com posicao_atual() ao final
- Se o comando for ambíguo, pergunte qual servo ou movimento desejado

Servos disponíveis e direções:
- base: DIREITA=ângulo menor (ex:45°) | ESQUERDA=ângulo maior (ex:135°) | frente=90°
- ombro: CIMA=ângulo maior (ex:130°) | BAIXO=ângulo menor (ex:45°)
- cotovelo: ESTICA=ângulo maior (ex:135°) | DOBRA=ângulo menor (ex:45°)
- pulso: ABRE=0° | FECHA=180°
- garra: rotação, neutro=90°

Entrada do usuário: $ARGUMENTS
