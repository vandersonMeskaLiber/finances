# Requisito do Finances

Versão 1, em 18 de outubro de 2026.

Este documento é o requisito do produto. Cada tela, daqui para a frente, nasce em três passos: contexto daquela tela, recorte deste requisito, e só então o desenvolvimento. Nada daqui autoriza construir tela agora.

A linha adotada abaixo já incorpora o que você pediu e o que sistemas parecidos fazem bem. Onde uma escolha muda o produto, ela está marcada como **linha adotada** e repetida na seção final, para você corrigir.

## 1. Produto

O Finances é um sistema de gestão financeira para a pessoa usar no navegador do computador, do celular e do tablet, e também instalar pelo próprio Chrome. A mesma base precisa caber, mais adiante, na App Store e na Play Store.

A pessoa enxerga o mês inteiro sem procurar: o saldo do mês, quanto entra, quanto sai, o que ainda está pendente e quanto foi investido. Cada lançamento diz em qual conta o dinheiro sai ou entra. A conta é um nome que a pessoa cria. Pode ser um banco, uma carteira, um cofre ou qualquer outro lugar. Não precisa ser uma instituição financeira. Dá para repetir contas fixas, acompanhar empréstimo, perseguir uma meta, simular uma decisão e, no contexto de pessoa jurídica, saber se o MEI está dentro do limite e se o imposto do mês foi pago.

Dois contextos convivem no mesmo login: pessoa física e pessoa jurídica. A estrutura é a mesma. Os dados não se misturam.

## 2. O que a pesquisa fixou nesta linha

Estes pontos vieram de produtos e métodos que já resolvem partes do que você descreveu. Eles entram no requisito porque evitam erro conhecido, não porque o produto vá copiar outro app.

- **Previsão do mês, dia a dia.** Organizze, Mobills, Minhas Economias e Calen tratam saldo previsto como função central. A capa do Finances segue essa linha: no dia 1 a pessoa vê o caminho até o último dia do mês.
- **Previsto e efetivado ficam visíveis ao mesmo tempo.** O método do YNAB alerta que tratar dinheiro que ainda não entrou como se já existisse quebra o plano. O Finances mostra a previsão, porque é isso que você pediu, e marca o que já aconteceu separado do que ainda é previsto.
- **Conta não mensal vira reserva mensal.** A segunda regra do YNAB divide uma despesa anual por 12. Isso alimenta metas: o sistema diz quanto guardar por mês para chegar na data.
- **Atraso de meta se corrige nos meses seguintes.** Se o mês ficou abaixo, o valor que falta se redistribui no prazo que resta. A meta final continua a mesma. É o mesmo raciocínio de um fundo de reserva com data.
- **Recorrência com duas edições.** Você pediu alterar só aquele mês ou alterar todas. O requisito segue isso. Ocorrência já paga não muda junto com a série, para o mês fechado não ser reescrito.
- **Empréstimo pessoal e consignado no Brasil usam Tabela Price.** A parcela é fixa. O SAC fica disponível porque a parcela cai e o juros total é menor, mas não é o padrão desses contratos. O sistema calcula a parcela, o juros, a amortização e o saldo devedor mês a mês. A taxa do contrato entra no cálculo. IOF, tarifa e seguro só entram se a pessoa informar, porque não estão na taxa mensal.
- **MEI em 2026.** O teto vigente é R$ 81.000,00 por ano. No ano de abertura, o teto é proporcional: R$ 6.750,00 por mês de atividade, contando o mês da abertura inteiro. Até 20% acima (R$ 97.200,00) há DAS complementar e a empresa vira microempresa no ano seguinte. Acima de 20%, o desenquadramento volta ao início do ano. O DAS vence no dia 20. Em 2026 o INSS do DAS é R$ 81,05, mais R$ 1,00 de ICMS e/ou R$ 5,00 de ISS. MEI transportador de cargas tem teto de R$ 251.600,00 e INSS de R$ 194,52. A DASN-SIMEI do ano anterior vence em 31 de maio. O Finances acompanha e alerta. Não emite guia e não entrega declaração.
- **Instalável agora, loja depois.** Chrome, Edge e Firefox instalam o sistema quando ele é servido em HTTPS, tem manifesto com nome, ícones de 192 e 512 pixels, `start_url` e `display` standalone. A Play Store aceita esse app embrulhado como Trusted Web Activity. A App Store não aceita um site reempacotado: o app precisa se comportar como aplicativo. Por isso nenhuma função pode depender de mouse, hover ou tela larga.

Fontes usadas na seção 18.

## 3. Atores

- **Administrador.** É você. Cria e desativa os logins, redefine acesso e altera as configurações do espaço, inclusive os contextos de pessoa física e pessoa jurídica.
- **Usuário.** É cada pessoa cujo login você criou. Lança, consulta, simula e acompanha metas dentro dos contextos que você liberou.

A primeira versão tem um espaço. Você é o administrador. Os demais entram com os logins que você criar. Os dados desse espaço nascem isolados de qualquer outro espaço. Cobrança, plano e vitrine ficam fora deste requisito. O isolamento existe desde já para o produto poder ser vendido sem misturar clientes.

## 4. Contextos pessoa física e pessoa jurídica

RF-CTX-01. No mesmo login a pessoa escolhe separar pessoa física e pessoa jurídica.

RF-CTX-02. Com a separação ligada, o sistema mostra um alternador sempre visível. A troca de contexto é imediata.

RF-CTX-03. Contas, lançamentos, tipos, metas, empréstimos, simulações e o resumo do mês pertencem a um contexto. Uma consulta de um contexto não lê o outro.

RF-CTX-04. A estrutura das telas é a mesma nos dois contextos. Muda o conjunto de dados.

RF-CTX-05. A área Empresa só aparece no contexto de pessoa jurídica.

RF-CTX-06. A pessoa pode usar só um dos contextos. O outro fica desligado até ela pedir.

## 5. Capa com resumo rápido

A capa é a primeira tela depois do login. Ela mostra o mês selecionado. O mês inicial é o mês corrente. Dá para ir ao mês anterior e ao seguinte.

### Números do topo

O topo mostra o resultado do mês e as quatro partes que formam esse resultado. Nenhum desses números detalha a conta. A conta aparece quando a pessoa abre o detalhe.

RF-CAPA-01. **Saldo** do mês = entradas − saídas − investimentos. Entram no cálculo o que já foi efetivado e o que ainda está previsto naquele mês.

RF-CAPA-02. **Entradas** do mês: soma das entradas, efetivadas e previstas. Investimento não entra aqui.

RF-CAPA-03. **Saídas** do mês: soma das saídas, efetivadas e previstas. Investimento não entra aqui.

RF-CAPA-04. **Pendências** do mês: o que ainda não foi efetivado. O card mostra, separados, o total a receber, o total a pagar e o total a investir.

RF-CAPA-05. **Investimentos** do mês: soma do que foi marcado como investimento naquele mês, efetivado e previsto. Não é cotação de ativo e não é o estoque acumulado de anos anteriores.

RF-CAPA-13. Transferência entre contas do mesmo contexto não entra em entrada, saída nem investimento. Ela só muda em qual conta o dinheiro está.

### Panorama dia a dia

RF-CAPA-06. Abaixo dos cards, o mês aparece dia a dia, do dia 1 ao último dia daquele mês.

RF-CAPA-07. Cada dia mostra as entradas, as saídas, os investimentos e o saldo acumulado até o fim daquele dia.

RF-CAPA-08. O saldo acumulado de um dia é a soma das entradas até aquele dia, menos as saídas até aquele dia, menos os investimentos até aquele dia. O dia 1 começa em zero. Este saldo é o resultado do mês, não a soma do dinheiro que já estava nas contas antes do mês.

RF-CAPA-09. Dia já passado usa o que foi efetivado. Dia de hoje e dias seguintes somam também o que está previsto e ainda não efetivado.

RF-CAPA-10. Cada movimento do dia mostra se está efetivado ou previsto.

RF-CAPA-11. No dia 1 a pessoa consegue ver o saldo do último dia do mês e em qual dia esse saldo acumulado cruza zero, se isso acontecer.

RF-CAPA-12. Abrir um dia leva aos lançamentos daquele dia. Abrir entradas, saídas, pendências ou investimentos leva à lista filtrada. No detalhe aparece a conta.

## 6. Onde está o dinheiro

A conta é o lugar do dinheiro. O nome é livre: Nubank, carteira, cofre, caixinha, um amigo, o caixa da empresa. Não existe cadastro obrigatório de banco nem lista de instituições financeiras.

RF-DIN-01. Toda entrada, toda saída e todo investimento informa a conta.

RF-DIN-02. A pessoa cria, renomeia e desativa contas. Cada conta pertence a um contexto.

RF-DIN-03. Cartão não é um tipo de lançamento. Tipo continua sendo a classificação que a pessoa cria, como alimentação e o subtipo dela. Cartão, quando a pessoa quiser controlar, é só uma conta com o nome que ela der, por exemplo "Cartão Nubank". A compra é um lançamento nessa conta, na data em que ela lançar.

RF-DIN-04. Não há fatura automática, fechamento nem vencimento calculado de cartão. Se a pessoa quiser registrar que pagou a fatura, ela lança isso na mão: uma transferência da conta que pagou para a conta do cartão, ou a saída que fizer sentido para ela.

RF-DIN-05. Cada conta tem saldo, formado pelos lançamentos dela: entradas somam, saídas diminuem, investimentos diminuem, transferência tira de uma e põe na outra.

RF-DIN-06. A tela de onde está o dinheiro lista as contas e o saldo de cada uma.

RF-DIN-07. No detalhe de um resumo, a pessoa vê quanto daquele valor está em cada conta.

## 7. Lançamento

RF-LAN-01. Um lançamento tem: contexto, data, valor, direção (entrada, saída, investimento ou transferência), conta, tipo, subtipo opcional, situação, descrição opcional e, quando fizer parte de uma repetição ou de um empréstimo, o vínculo com essa origem. Investimento não pede tipo.

RF-LAN-02. Valor é sempre maior que zero. A direção diz se entra ou sai. O sistema guarda centavos, sem fração de centavo.

RF-LAN-03. Transferência pede conta de origem e conta de destino, no mesmo contexto, diferentes entre si.

### Contas fixas e repetição

RF-LAN-04. A pessoa programa uma saída ou uma entrada que se repete todo mês, num dia escolhido.

RF-LAN-05. Se o dia escolhido não existe naquele mês, a ocorrência cai no último dia do mês.

RF-LAN-06. A repetição tem prazo: uma quantidade de meses, como 5 ou 48, ou fica ativa até a pessoa encerrar.

RF-LAN-07. Cada ocorrência nasce como lançamento previsto, na conta escolhida, com tipo e subtipo quando a direção usar tipo.

RF-LAN-08. Ao editar uma ocorrência, o sistema pergunta:

- alterar só este lançamento;
- alterar todas as ocorrências da série.

RF-LAN-09. "Só este" desliga aquela ocorrência da série. As outras continuam iguais.

RF-LAN-10. "Todas" altera a regra e as ocorrências que ainda não foram efetivadas. Ocorrência já paga ou já recebida permanece como está.

RF-LAN-11. Encerrar a série pede a partir de qual mês. Ocorrências já efetivadas permanecem.

RF-LAN-12. Neste requisito a repetição é mensal. Semanal, quinzenal e anual ficam fora.

## 8. Tipagem e situação

RF-TIP-01. Tipo e subtipo são criados pela pessoa. O sistema não traz lista pronta de alimentação, moradia ou qualquer outro nome.

RF-TIP-02. Um tipo pertence a um contexto e serve para entrada ou saída. Transferência e investimento não usam tipo.

RF-TIP-03. O subtipo é opcional e pertence a um tipo. A pessoa pode lançar só com o tipo.

RF-TIP-04. A pessoa cria, renomeia, reordena e desativa tipo e subtipo. Desativar esconde dos lançamentos novos e preserva os antigos.

RF-TIP-05. Consultas agrupam pelo tipo e abrem o subtipo.

RF-SIT-01. Entrada tem situação a receber ou recebido. Saída tem situação a pagar ou pago.

RF-SIT-02. A pessoa marca e desmarca a efetivação. A data de efetivação pode ser diferente da data prevista.

RF-SIT-03. Lançamento não efetivado com data anterior a hoje aparece como atrasado. Atraso é calculado, não é uma situação gravada à parte.

RF-SIT-04. Uma ocorrência pode ser cancelada. Cancelado sai dos totais e do panorama e continua visível no histórico da série.

## 9. Empréstimo

RF-EMP-01. Um empréstimo é um contrato de um contexto, ligado à conta de onde a parcela sai. Dívida em dois lugares são dois contratos. A tela de empréstimos soma os contratos.

RF-EMP-02. Para chegar na parcela e na evolução, o contrato guarda:

- valor tomado;
- taxa de juros mensal;
- prazo em meses ou valor da parcela, quando um dos dois for o dado que a pessoa tem;
- sistema: Tabela Price, como padrão, ou SAC;
- data da primeira parcela;
- quantas parcelas já foram pagas, se o contrato começou antes de entrar no sistema;
- conta de onde a parcela sai.

RF-EMP-03. Na Tabela Price a parcela é fixa: valor vezes a taxa mensal, dividido por um menos (1 mais a taxa) elevado a menos o número de meses. Em cada mês, o juros é o saldo devedor vezes a taxa, e o resto da parcela amortiza.

RF-EMP-04. No SAC a amortização mensal é o valor tomado dividido pelo número de meses. A parcela do mês é essa amortização mais o juros do saldo. A parcela diminui.

RF-EMP-05. Se a pessoa informar valor, taxa e parcela, o sistema calcula o prazo e mostra o saldo que sobra na última parcela por causa do arredondamento de centavos.

RF-EMP-06. Se a pessoa informar valor, taxa e prazo, o sistema calcula a parcela.

RF-EMP-07. O resultado mostra, mês a mês: parcela, juros, amortização e saldo devedor. Mostra também o total de juros e o total a pagar.

RF-EMP-08. O contrato gera as parcelas como saídas previstas da série, na conta escolhida, no tipo que a pessoa indicar. Pagar a parcela no lançamento atualiza a evolução do contrato.

RF-EMP-09. Quitar, antecipar ou mudar taxa, prazo ou parcela recalcula o que ainda não foi pago e pergunta se a série futura deve ser atualizada. Parcelas já pagas ficam no histórico com o valor pago.

RF-EMP-10. IOF, tarifa e seguro não são inventados pela taxa. Se a pessoa informar esses valores, eles entram no total do contrato e podem virar saída à parte. O custo efetivo total só é exibido quando esses valores existem.

## 10. Metas e desafios

RF-MET-01. Uma meta tem nome, valor alvo, data alvo e contexto.

RF-MET-02. O sistema calcula quanto falta guardar por mês: (alvo menos o já guardado) dividido pelos meses que restam, incluindo o mês corrente. O resultado é o desafio daquele mês.

RF-MET-03. O valor guardado no mês é informado pela pessoa, na hora. O sistema não deduz isso de transferência nem da sobra de entradas menos saídas.

RF-MET-04. Cada mês da meta guarda: quanto era o desafio, quanto foi guardado, a diferença e se bateu.

RF-MET-05. Se o mês ficou abaixo, a diferença entra no cálculo dos meses seguintes. O alvo e a data permanecem. O desafio mensal sobe.

RF-MET-06. Se o mês ficou acima, o excesso reduz o desafio dos meses seguintes.

RF-MET-07. A pessoa pode mudar o alvo ou a data. O histórico dos meses já encerrados permanece. O desafio dos meses abertos é recalculado.

RF-MET-08. Meta concluída mostra o total guardado e quantos meses bateram.

## 11. Simulação

RF-SIM-01. A simulação ajuda a decidir sem gravar lançamento.

RF-SIM-02. A base da simulação é o panorama do mês escolhido, com as contas fixas e as parcelas já existentes, mais o valor que a pessoa diz que consegue economizar.

RF-SIM-03. A pessoa pode testar, juntos ou separados:

- uma parcela nova, com valor e dia;
- um empréstimo novo, com valor, taxa, prazo ou parcela, e ver a parcela calculada entrar no mês;
- tirar ou reduzir um gasto recorrente;
- incluir ou reduzir uma entrada.

RF-SIM-04. O resultado mostra o panorama dia a dia com a hipótese, o saldo do último dia e se algum dia fica negativo.

RF-SIM-05. O resultado também mostra a parcela nova ao lado do que sobra no mês depois das saídas já comprometidas.

RF-SIM-06. A simulação some quando a pessoa sai dela, a menos que ela peça para transformar a hipótese em lançamento ou em empréstimo de verdade. Essa transformação passa pelas mesmas regras de lançamento e de empréstimo.

## 12. Empresa

A área Empresa fica dentro do contexto de pessoa jurídica. Não há login, entrada nem tipo de usuário próprio para ela.

RF-EMPR-01. A pessoa informa o perfil: MEI comum, MEI transportador de cargas, ou outro teto informado por ela. O padrão do MEI comum em 2026 é R$ 81.000,00 por ano. O padrão do transportador é R$ 251.600,00. O teto é configurável para a lei mudar sem esperar uma versão nova.

RF-EMPR-02. No ano de abertura, o teto usado é o proporcional aos meses de atividade, contando o mês de abertura como mês cheio. Para o MEI comum, R$ 6.750,00 por mês de atividade.

RF-EMPR-03. O faturamento do ano é a soma das entradas do contexto de pessoa jurídica naquele ano-calendário. A pessoa pode marcar uma entrada como "não entra no faturamento" quando o dinheiro não for receita bruta.

RF-EMPR-04. A área mostra o faturamento acumulado, o teto, o quanto falta e o percentual usado.

RF-EMPR-05. Alertas:

- ao passar de 80% do teto;
- ao atingir o teto;
- ao passar de 20% acima do teto. A mensagem explica os dois cenários vigentes: até 20% acima, DAS complementar e mudança para microempresa no ano seguinte; acima de 20%, desenquadramento desde o início do ano ou da abertura.

RF-EMPR-06. O sistema não calcula o imposto de microempresa nem de empresa de pequeno porte. Se o teto estoura, a orientação é procurar contador. Os limites de referência, para texto de ajuda, são R$ 360.000,00 para microempresa e R$ 4.800.000,00 para empresa de pequeno porte.

RF-EMPR-07. DAS do mês: a pessoa vê os doze meses do ano, o vencimento no dia 20 e a situação pago ou não pago. O valor sugerido em 2026 é R$ 81,05 de INSS, mais R$ 1,00 se houver ICMS e mais R$ 5,00 se houver ISS. Transportador sugere INSS de R$ 194,52 mais os mesmos adicionais. A pessoa confirma as atividades e pode corrigir o valor. Pagar o DAS gera, se ela quiser, a saída correspondente na conta que ela escolher.

RF-EMPR-08. DASN-SIMEI: lembrete de que a declaração do ano anterior vence em 31 de maio, mesmo sem faturamento. A pessoa marca como entregue. O sistema não preenche nem transmite a declaração. Se o prazo legal mudar, a data do lembrete é configurável.

RF-EMPR-09. Nada nesta área emite boleto, nota ou guia, e nada substitui o Portal do Simples Nacional.

## 13. Segurança e comercialização

RF-SEG-01. Sem login não há dado. Toda tela pede sessão válida.

RF-SEG-02. O administrador cria login, desativa login e dispara redefinição de senha. Usuário desativado não entra, e o histórico dele permanece.

RF-SEG-03. Senha não é guardada em texto puro.

RF-SEG-04. Um espaço não lê dados de outro espaço. Dentro do espaço, pessoa física não lê pessoa jurídica.

RF-SEG-05. O acesso é sempre por HTTPS.

RF-SEG-06. A pessoa pode exportar os dados do próprio espaço e pode pedir a exclusão deles. Isso deixa o produto alinhado à LGPD antes de ser vendido.

RF-SEG-07. Cobrança, nota fiscal do próprio produto e página de planos ficam fora deste requisito.

## 14. Plataforma e desempenho

RF-PLT-01. Uma única interface serve computador, tablet e celular no navegador. A capa, o panorama do mês e o lançamento cabem e funcionam nos três, sem depender de hover.

RF-PLT-02. O sistema é instalável pelo Chrome como aplicativo: manifesto, ícones de 192 e 512 pixels, abertura em janela própria e HTTPS. O mesmo vale para os navegadores que seguem esse critério.

RF-PLT-03. Nada da interface exige uma função que só exista no computador. Isso é o que permite, depois, embrulhar o mesmo produto para a Play Store e para a App Store.

RF-PLT-04. A capa do mês, com um ano de lançamentos no espaço, abre em menos de um segundo em uma conexão 4G de celular. A troca de mês e a troca entre pessoa física e pessoa jurídica obedecem o mesmo limite.

RF-PLT-05. A capa pede o mês, não o histórico inteiro. Totais do mês são calculados para aquele intervalo.

RF-PLT-06. Valores são inteiros em centavos. A tela formata em real.

## 15. Modelo conceitual

Estes são os conceitos, não o desenho do banco.

- **Espaço.** O ambiente cujo administrador é você. Isola todos os dados.
- **Usuário.** Login criado por você, com papel de administrador ou usuário.
- **Contexto.** Pessoa física ou pessoa jurídica, dentro do espaço.
- **Conta.** Nome livre, de um contexto, com saldo. Pode ser banco, carteira ou qualquer outro lugar.
- **Tipo e subtipo.** Configurados pela pessoa, por contexto e direção.
- **Lançamento.** Movimento de uma data, com situação e conta.
- **Série.** Regra mensal que gera lançamentos.
- **Empréstimo.** Contrato que gera uma série de parcelas e guarda a evolução.
- **Meta.** Alvo com data, desafio mensal e histórico.
- **Simulação.** Hipótese temporária sobre o panorama.
- **Perfil da empresa.** Teto, atividades do DAS e situação da declaração, só no contexto jurídico.

## 16. Fora deste requisito

- Open Finance, lista obrigatória de bancos e importação automática de extrato.
- Fatura automática de cartão, com fechamento e vencimento calculados.
- Cotação de bolsa, fundo ou cripto.
- Emissão de DAS, nota fiscal ou DASN.
- Cálculo de imposto de microempresa e de empresa de pequeno porte.
- Repetição que não seja mensal.
- Cobrança de assinatura do próprio Finances.
- Publicação nas lojas. O requisito só impede decisões que bloqueiem essa publicação.

## 17. Critério de aceite por área

- **Contextos.** Com os dois ligados, um lançamento da pessoa física não aparece na pessoa jurídica, e o alternador troca o panorama na hora.
- **Capa.** No dia 1 estão visíveis o saldo (entradas − saídas − investimentos), as entradas, as saídas, as pendências e os investimentos, além de todos os dias do mês. Dá para apontar o saldo do último dia.
- **Dinheiro.** Uma saída sem conta não é salva. A conta pode se chamar "Carteira" sem estar ligada a um banco. O detalhe de uma entrada mostra a conta.
- **Série.** Uma parcela de 5 meses gera 5 previstos. Alterar só um não muda os outros. Alterar todas não muda o que já foi pago.
- **Empréstimo.** Valor, taxa mensal e prazo produzem a parcela Price e a tabela até o saldo zerar. Pagar uma parcela reduz o saldo devedor.
- **Meta.** Com alvo e data, o sistema diz o valor do mês. A pessoa informa quanto guardou. Um mês abaixo aumenta o desafio dos meses seguintes e mantém o alvo.
- **Simulação.** Incluir uma parcela hipotética muda o panorama e não cria lançamento até a pessoa confirmar.
- **Empresa.** O faturamento do ano comparado ao teto de R$ 81.000,00 dispara os três alertas nos pontos certos. O DAS de um mês pode ser marcado como pago.
- **Acesso.** Sem login a capa não abre. Usuário de um espaço não vê outro espaço.
- **Plataforma.** A capa é utilizável no celular e é instalável pelo Chrome.

## 18. Referências

- Teto do MEI e proposta ainda não vigente: [gov.br/memp/pt-br/teto-do-mei](https://www.gov.br/memp/pt-br/teto-do-mei)
- DAS 2026: [Receita Federal, Simples Nacional, 02/01/2026](https://www8.receita.fazenda.gov.br/simPlesnacional/Noticias/NoticiaCompleta.aspx?id=c3b2044c-ff97-432a-b33c-ecf2a3df6dc3) e [Agência Brasil](https://agenciabrasil.ebc.com.br/economia/noticia/2026-01/recolhimento-do-mei-sobe-para-r-8105-em-2026)
- DASN-SIMEI até 31 de maio: [gov.br, declaração anual](https://www.gov.br/empresas-e-negocios/pt-br/empreendedor/servicos-para-mei/declaracao-anual-de-faturamento) e agenda da Receita em 31/05/2026
- Limites de microempresa e empresa de pequeno porte: perguntas frequentes do DREI, em gov.br/empresas-e-negocios
- Quatro regras do YNAB: [ynab.com/guide/stop-living-paycheck-to-paycheck](https://www.ynab.com/guide/stop-living-paycheck-to-paycheck)
- Lançamentos agendados e repetição: [suporte do YNAB](https://support.ynab.com/en_us/scheduled-transactions-a-guide-BygrAIFA9.md)
- Previsão dia a dia nos apps brasileiros: comparação Calen, Mobills, Organizze e Minhas Economias em [usecalen.com.br](https://usecalen.com.br/melhores-apps-de-controle-financeiro), conferida pelos autores em 23/09/2026; contas a pagar em [Exame](https://exame.com/tecnologia/examelab/os-5-melhores-apps-para-organizar-contas-e-nunca-mais-esquecer-um-boleto/)
- Tabela Price e SAC: fórmula da parcela fixa e da amortização constante, como em calculadoras públicas de financiamento (calcfolio, Even Figures, QMIX)
- App instalável: [web.dev, install criteria](https://web.dev/articles/install-criteria)
- Lojas a partir de um app web: [progressivewebapps.com, setembro de 2026](https://progressivewebapps.com/installation/app-stores/), inclusive a regra 4.2 da Apple contra site reempacotado

## 19. Decisões fechadas

Confirmadas em 18 de outubro de 2026:

1. Você é o administrador. Os outros acessos são usuários que você cria.
2. Lançamento manual. Sem Open Finance.
3. Conta é um nome livre. Não precisa ser instituição financeira.
4. Cartão não é tipo de lançamento e não tem fatura automática. Se for controlado, é uma conta com o nome que você der.
5. O saldo da capa é entradas − saídas − investimentos do mês. Ao lado entram entradas, saídas, pendências e investimentos.
6. Na meta, você informa quanto guardou. O sistema não calcula isso sozinho.
7. Repetição só mensal.
8. Empréstimo em Tabela Price por padrão, um contrato por conta.
9. Empresa só no contexto de pessoa jurídica, como acompanhamento, sem emitir guia.
