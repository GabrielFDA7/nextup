# Prompt para o Claude Design — Fase 9.3

Escrito em 27/10/2026 para gerar a nova interface no Claude Design. Fica versionado
porque o redesenho continua em outra máquina, e o prompt é o resumo mais completo do que
a tela precisa transmitir: a tese do produto, os dados reais da API e as regras de
comportamento que o código já garante.

**Primeira rodada (28/10/2026):** o Gabriel gerou as telas e não gostou tanto do
resultado, mas vai aproveitar muita coisa. Ao revisar o que voltar, conferir cada elemento
contra o que a API realmente entrega (seção "Os dados que cada atração tem").

**Decisão de estrutura:** uma tela principal com uma camada transitória por cima, e não
duas páginas. O app abre mostrando o parque antes de pedir qualquer coisa (regra da Fase
5); um cadastro em página separada faria o visitante, no meio do parque, preencher
formulário antes de ver qualquer resposta.

---

```
Quero que você desenhe a interface mobile de um web app chamado NextUp. Leia o contexto
inteiro antes de desenhar: a parte mais importante deste pedido é entender o que o
produto faz de diferente, porque isso define a hierarquia da tela.

## O que é o NextUp

Um assistente para quem está DENTRO do Magic Kingdom (Walt Disney World, Orlando) e se
pergunta: "para onde eu vou agora?". Hoje esse serviço é feito à mão por consultores de
parque, por WhatsApp. O NextUp automatiza esse consultor.

A tese do produto, que a tela precisa transmitir:

1. Ver o tempo de fila NÃO resolve o problema. Qualquer app mostra as filas, e qualquer
   pessoa compara números de cabeça. O NextUp responde o que o visitante não consegue
   calcular sozinho.
2. O critério é o tempo total até estar no brinquedo: caminhada + fila. Nunca a menor
   fila isolada. A menor fila pode estar a 15 minutos de caminhada, e o visitante andaria
   15 para economizar 10.
3. A resposta depende de quem pergunta. Uma família com criança de 90 cm e um grupo de
   adolescentes atrás de adrenalina recebem respostas diferentes, no mesmo parque e na
   mesma hora.
4. Ordem importa mais que a parada isolada. Quem quer fazer 5 atrações favoritas economiza
   tempo seguindo um roteiro que não atravessa o parque e volta. (Medido: 162 min contra
   173 seguindo a ordem "mais barata agora", com 11 minutos a menos de caminhada.)

O tom é o de um amigo que conhece o parque de cor: direto, confiante, sem jargão, e
honesto quando não sabe. Ele explica o porquê de cada sugestão em uma frase.

## Quem usa, e em que condições

- No celular, em pé, no meio do parque, muitas vezes com uma mão só (a outra segura
  criança, bebida ou carrinho).
- Sol forte da Flórida na tela: contraste alto importa mais que sutileza.
- Uso em rajadas de 10 a 20 segundos: abre, decide, guarda o celular, anda.
- Famílias com crianças pequenas, casais, grupos de amigos, visitantes de primeira viagem.
- Brasileiros. Todo o texto da interface em português do Brasil. Os nomes das atrações
  ficam no original em inglês, como aparecem no parque.

## O que desenhar: uma tela, dois estados

Não é um site de várias páginas. É uma tela principal com uma camada transitória.

### Estado 1: primeira abertura

O parque aparece imediatamente (mapa do Magic Kingdom ao fundo). Por cima, um painel
leve, nunca um formulário de cadastro, com SÓ duas perguntas, ambas puláveis:

  a) "Tem criança no grupo? Qual a altura da mais baixa?" (em cm; opção "sem crianças")
  b) "Que tipo de atração vocês curtem?": Tranquilas / De tudo um pouco / Quero emoção

Quem pular recebe o app sem restrição nenhuma. O painel precisa deixar claro POR QUE
pergunta ("para não te mandar para uma fila em que a criança não pode entrar"), porque
pergunta sem motivo parece coleta de dado. Não existe login, conta ou e-mail: tudo fica
no próprio celular. O perfil pode ser editado depois, a partir de um resumo compacto na
tela principal (por exemplo: "Com criança de 95 cm · De tudo um pouco").

O app também pede a localização. Se o visitante negar, ele toca no mapa para dizer onde
está. Essa alternativa precisa ser óbvia, não escondida.

### Estado 2: a tela principal, em uso

Hierarquia, nesta ordem de importância:

1. SEU PRÓXIMO PASSO. Uma única atração, em destaque, com:
   - o tempo total grande (ex.: "12 min"), decomposto em "7 a pé + 5 de fila";
   - uma frase de porquê (ex.: "Uma das principais do parque, e hoje bem abaixo da média
     dela");
   - um botão "Já fui", que marca a atração como feita hoje e passa para a próxima.

2. SEU ROTEIRO, para quem marcou atrações favoritas ("alvos"). Uma linha do tempo com as
   próximas 3 a 5 paradas na ordem sugerida, com horário estimado de chegada e uma pista
   de por que essa ordem ("a TRON fica ao lado da Space Mountain"). Ele se refaz a cada
   parada concluída. É uma sugestão viva, não um plano rígido do dia.

3. O MAPA, com as sugestões numeradas e a posição do visitante.

4. VER TODAS AS FILAS, rebaixado para secundário (um painel expansível ou uma aba). É a
   lista completa, com filtros de "fila máxima" e "caminhada máxima". Existe, mas não é o
   produto.

## Os dados que cada atração tem (use estes, são reais)

- tempo de caminhada em minutos, a partir da posição do visitante
- fila em minutos (pode ser desconhecida: atração aberta sem fila medida)
- popularidade: "uma das principais" / mediana / "tranquila" / desconhecida
- "oportunidade": uma das principais com fila hoje abaixo da média dela. É o selo que
  mais importa, porque é informação que só o NextUp tem.
- tendência da fila: subindo / caindo / estável (ex.: "caiu de 45 para 20 na última
  meia hora")
- altura mínima em cm (ex.: TRON 122, Space Mountain 112, Tiana's Bayou Adventure 102,
  Big Thunder 97, Seven Dwarfs 97, Barnstormer 89)
- intensidade: tranquila / moderada / radical
- marcas do visitante: "alvo" (quero fazer) e "já fui hoje"

Exemplo realista para popular as telas (filas de uma noite real, visitante perto da
entrada):
- Space Mountain: 7 a pé + 5 de fila, principal, oportunidade, radical, 112 cm
- TRON Lightcycle / Run: 9 a pé + 40 de fila, principal, radical, 122 cm
- Seven Dwarfs Mine Train: 8 a pé + 30 de fila, principal, radical, 97 cm
- Peter Pan's Flight: 8 a pé + 20 de fila, principal, moderada
- Big Thunder Mountain Railroad: 10 a pé + 5 de fila, principal, oportunidade, radical, 97 cm
- Jungle Cruise: 6 a pé + 5 de fila, principal, oportunidade, tranquila
- Dumbo the Flying Elephant: 9 a pé + 5 de fila, tranquila
Roteiro sugerido para esses 5 alvos: Space Mountain → TRON → Seven Dwarfs → Peter Pan →
Big Thunder (162 min no total).

## Regras de comportamento que a tela precisa respeitar

- Atração em que a criança do grupo NÃO pode entrar continua aparecendo, marcada como
  "a partir de 122 cm · só os adultos". O grupo pode se revezar (o Rider Switch da
  Disney). Ela NUNCA ganha o destaque de "seu próximo passo", que é para o grupo todo.
- A preferência de intensidade filtra, e o filtro precisa ser visível. Filtro esquecido
  é indistinguível de parque vazio: se algo está escondido, a tela diz quanto e por quê,
  com um jeito rápido de desfazer.
- Dado desconhecido é mostrado como desconhecido. Nunca como "tranquila" nem como
  "fila zero".
- Lista vazia tem três causas diferentes, e cada uma tem sua frase: os filtros estão
  apertados demais; o visitante já passou por todas; o parque está fechado.
- Dado velho precisa ser visível ("filas de 12 minutos atrás"), porque fila defasada
  apresentada como atual faz o visitante decidir errado.

## Identidade visual

A versão atual usa "personalidade de parque": paleta de pôr do sol (coral, âmbar, roxo
profundo), fonte Outfit, cantos arredondados, ícones SVG e marcadores numerados no mapa.
Use isso como ponto de partida, não como prisão. Quero ver a proposta mais criativa que
você conseguir, desde que funcione no sol forte e com uma mão. Desenhe também o tema
escuro (uso à noite, nos fogos).

Restrição importante: o NextUp é um projeto independente, SEM vínculo com a Disney. Não
use logotipos, personagens, orelhas do Mickey, a silhueta do castelo, nem fontes ou
grafismos que imitem a marca Disney. A magia tem que vir do nosso próprio desenho.

## Restrições técnicas

- Mobile first (390 px de largura como referência). No desktop, a mesma interface
  centralizada basta.
- Vai ser implementado em HTML, CSS e JavaScript puros, sem framework e sem etapa de
  build. O mapa é Leaflet com OpenStreetMap. Prefira o que dá para fazer em CSS: nada de
  efeito que exija biblioteca de animação.
- Acessível: contraste AA no mínimo, alvos de toque de 44 px ou mais, e informação nunca
  transmitida só por cor (o selo de altura e o de intensidade precisam de texto ou ícone).

## O que eu quero receber

1. O Estado 1 (primeira abertura com o painel do perfil), claro e escuro.
2. O Estado 2 (tela principal em uso, com perfil "criança de 95 cm · de tudo um pouco" e
   os 5 alvos acima), claro e escuro.
3. Os componentes isolados: o cartão do "próximo passo", uma parada do roteiro, um item da
   lista de filas, e os selos (oportunidade, altura, intensidade, tendência).
4. Dois estados de borda: visitante que negou o GPS, e lista vazia por filtro apertado.
5. Uma nota curta explicando as suas escolhas de hierarquia e de identidade.
```
