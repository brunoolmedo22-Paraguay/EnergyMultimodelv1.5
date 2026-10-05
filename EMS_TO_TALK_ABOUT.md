# EMS — To talk about com Marília

Itens deliberadamente **não alterados** nesta primeira integração porque mexem na metodologia do EMS e devem ser discutidos antes de modificar a lógica original.

1. **Excedente solar/eólico → bateria antes do curtailment**  
   Hoje solar e eólica são must-take e o excedente acima da carga é vertido antes do EMS. Avaliar futuramente permitir carregamento da bateria com esse excedente.

2. **Escolha e efeito do horizonte N**  
   A correção de cobertura até o último minuto já foi feita. Continua pendente discutir qual N representa melhor a operação e o impacto econômico de horizontes curtos/longos.

3. **Partidas/desligamentos da PEMFC**  
   Hoje não há custo explícito de start/stop, minimum-up/down time nem degradação por ciclo de partida.

4. **Degradação eletroquímica e flutuação da FC**  
   Os termos presentes na referência MATLAB antiga não entram na função objetivo Python ativa. Decidir se devem voltar e como parametrizá-los fisicamente.

5. **Rampa e número anterior de stacks**  
   A lógica atual infere o número anterior de unidades a partir da potência anterior em parte das restrições. Avaliar usar diretamente o estado discreto anterior (`n_prev`).

> Fora de escopo desta lista por decisão do projeto: discutir academicamente se GA/GWO/NGO agregam valor frente ao SQP puro. O código permanece como recebido.
