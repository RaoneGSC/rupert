Rotina de calibração visual do Rupert — percorre o range de cada servo com feedback de câmera.

Execute esta sequência completa:

1. Chame status_conexao() no MCP rupert para verificar se o Pico está conectado
2. Chame iniciar_monitoramento(intervalo_s=0.5) no MCP rupert-vision
3. Chame centralizar() para colocar o Rupert em posição neutra de referência
4. Captura frame inicial com capturar_frame() — esta é a referência

Para cada servo em ordem (base, ombro, cotovelo, pulso, garra):
  a. Mova para o ângulo mínimo (ANGLE_MIN + 10°) com mover_servo()
  b. Chame aguardar_movimento_parar()
  c. Capture frame e analise: o braço se moveu na direção esperada?
  d. Mova para 90° (neutro)
  e. Chame aguardar_movimento_parar()
  f. Mova para o ângulo máximo (ANGLE_MAX - 10°)
  g. Chame aguardar_movimento_parar()
  h. Capture frame e analise: o braço se moveu na direção oposta?
  i. Retorne ao neutro (90°)
  j. Registre: OK se movimento foi visível, PROBLEMA se não houve mudança na imagem

5. Chame parar_monitoramento()
6. Gere relatório final:
   - Servos OK: lista
   - Servos com problema: lista + descrição do problema observado
   - Recomendações de ajuste se necessário
