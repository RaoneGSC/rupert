Fluxo de análise visual do Rupert usando webcam + controle de servos.

Execute este fluxo completo:

1. Chame iniciar_monitoramento(intervalo_s=0.5) no MCP rupert-vision para ativar câmera
2. Chame capturar_frame() e analise visualmente: posição do braço, se está segurando algo, postura geral
3. Se recebeu um objetivo ($ARGUMENTS):
   a. Planeje os movimentos necessários via MCP rupert (mover_servo ou mover_sequencia)
   b. Execute cada movimento
   c. Após cada movimento, chame aguardar_movimento_parar(timeout_s=6.0)
   d. Em seguida, chame obter_frame_atual() e analise visualmente o resultado
   e. Se não alcançou o objetivo, faça ajuste fino e repita a partir de (b)
4. Se nenhum objetivo foi passado, apenas descreva o que vê na imagem
5. Reporte o resultado final com descrição da posição observada
6. Chame parar_monitoramento() ao terminar

Seja preciso na análise visual: descreva ângulos aparentes, posição relativa dos segmentos do braço, e se o movimento foi bem-sucedido.

Objetivo: $ARGUMENTS
