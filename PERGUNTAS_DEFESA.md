# Banco de perguntas para a defesa/apresentação

Este banco cobre as perguntas mais prováveis que o professor pode fazer
sobre este trabalho, combinando (1) os requisitos explícitos do enunciado e
(2) os conceitos do slide de aula "Sistemas de Arquivos" (Pedro de Botelho
Marcos). As perguntas são genéricas — do tipo que ele poderia fazer para
qualquer grupo, não são "pegadinhas" específicas do nosso código — mas cada
uma vem com um resumo de como responder **usando a nossa implementação**,
com o arquivo/trecho de código onde a resposta está, para vocês
consultarem no preparo e responderem com as próprias palavras (não decorem
a resposta pronta — expliquem o porquê).

Estão organizadas da **mais** para a **menos** prioritária (maior
probabilidade de cair primeiro). Como a dinâmica é de 4 perguntas por
integrante, o ideal é todo mundo saber responder pelo menos as ~16
primeiras (Camadas 1 e 2); as demais são para aprofundar/hedge.

---

## Camada 1 — Estrutura e requisitos centrais (altíssima probabilidade)

**1. Quais campos tem o i-node de vocês e por quê cada um está lá?**
Nome, criador, dono, tamanho, data de criação, data de modificação,
permissões (dono + outros, rwx), 8 ponteiros diretos e `next_inode` — mais
dois campos de controle (`used`, `type`) não pedidos explicitamente mas
necessários para saber se o i-node está ocupado e se é arquivo/diretório/
link. Ver `fs/structs.py:88-101` (classe `Inode`) e o formato binário em
`fs/constants.py:20-22` (`INODE_FORMAT`).

**2. Que tamanho tem cada i-node, e por que esse tamanho foi escolhido?**
128 bytes, potência de dois (exigência do enunciado). O cálculo é feito por
`struct.calcsize` sobre o formato empacotado e validado por
`assert INODE_SIZE == 128` em `fs/constants.py:23-25` — se alguém mudar um
campo e o tamanho deixar de ser potência de 2, o programa nem inicia.

**3. Como o disco de 128 MB está organizado por dentro (layout de blocos)?**
Bloco 0 = superbloco; bloco 1 = bitmap de i-nodes; blocos 2–5 = bitmap de
blocos de dados; blocos 6–517 = tabela de i-nodes (8192 × 128 B = 1 MiB);
518 em diante = área de dados (~127 MB). Todo o layout é calculado (não
"chutado") em `fs/constants.py:59-78`, com `assert`s garantindo que a soma
fecha exatamente em 128 MB.

**4. Como o sistema sabe quais blocos e quais i-nodes estão livres ou
ocupados?**
Um bitmap para cada um (`fs/bitmap.py`): um bit por bloco/i-node, 1 =
ocupado. O bitmap de i-nodes tem 8192 bits (1 KB), o de blocos tem 65536
bits (8 KB). Os bitmaps ficam em memória durante a execução e cada
alteração é persistida imediatamente no disco (só o bloco do bitmap que
mudou, não o bitmap inteiro — ver `_save_inode_bitmap_bit`/
`_save_block_bitmap_bit` em `fs/filesystem.py:176-188`).

**5. O sistema é realmente persistente? Como vocês comprovam isso?**
Sim — toda alteração (bitmaps, superbloco, i-nodes, blocos de dados) é
escrita direto no arquivo de disco a cada operação, e o shell chama
`flush()`/`fsync()` ao fim de cada comando (`fs/shell.py:79`,
`fs/disk.py:49-51`). Para comprovar: rodar o programa, criar arquivos,
sair (`exit`), abrir de novo apontando pro mesmo arquivo de disco e ver que
tudo continua lá — é a Seção 12 do `ROTEIRO_DE_TESTES.md`.

**6. Por que vocês usaram o módulo `struct` em vez de JSON/pickle para
salvar os dados?**
Porque o enunciado proíbe explicitamente JSON, e porque um sistema de
arquivos de verdade grava estruturas de **tamanho fixo em binário** (não
texto), permitindo endereçar qualquer i-node/bloco por cálculo de posição
(`num * INODE_SIZE`) em vez de ter que reler um arquivo texto inteiro.
`fs/structs.py` mostra o pack/unpack de cada estrutura.

**7. Que operações vocês implementaram e onde estão no código?**
Arquivos: `touch`, `rm`, `echo "..." >`, `echo "..." >>`, `cat`, `cp`, `mv`,
`ln -s`. Diretórios: `mkdir`, `rmdir` (só se vazio), `ls`, `cd` (com `.` e
`..`), `mv`, `ln -s`. Todas em `fs/filesystem.py` (métodos com o mesmo
nome, ex. `touch()`, `mkdir()`); o shell (`fs/shell.py`) só faz o parsing
da linha de comando e chama esses métodos.

**8. Os comandos funcionam com caminho absoluto e relativo?**
Sim — tudo passa por um único resolvedor de caminho, `resolve()` em
`fs/filesystem.py:592-623`: se o caminho começa com `/`, parte da raiz; caso
contrário, parte do diretório atual (`cwd_inode`). `.` e `..` são entradas
reais gravadas em todo diretório (ver pergunta 12).

---

## Camada 2 — Alocação de espaço e crescimento de arquivos (alta probabilidade)

**9. Como funciona a alocação de blocos de um arquivo? Vocês usam alocação
contígua, lista encadeada, FAT ou baseada em índice (i-nodes)?**
Baseada em i-node, como no UNIX clássico: cada i-node guarda até 8
ponteiros diretos para blocos de dados (cobrindo 16 KB). É o esquema visto
no slide de "Implementando arquivos" — evita a fragmentação da alocação
contígua e o acesso lento da lista encadeada pura, sem precisar de uma
tabela gigante como a FAT (ver pergunta 11).

**10. O que acontece quando um arquivo passa de 16 KB (os 8 ponteiros
diretos não bastam mais)?**
Em vez de um bloco de ponteiros indiretos (como o UNIX clássico faz), o
i-node tem um campo `next_inode`: quando os 8 ponteiros enchem, aloca-se um
**outro i-node de continuação** (mesma estrutura, mais 8 ponteiros) e o
`next_inode` do anterior passa a apontar pra ele, formando uma cadeia. Isso
é literalmente o "apontador para eventual outro i-node" pedido no
enunciado. Implementado em `_chain()`/`_grow()`/`_shrink()`,
`fs/filesystem.py:257-382`. O tamanho máximo de um arquivo só é limitado
pelos blocos/i-nodes livres do disco, não por um teto fixo.

**11. Por que vocês não usaram uma tabela FAT (todos os blocos numa tabela
única em memória)?**
Porque não escala: no slide é mostrado que um disco de 200 GB com blocos
de 1 KB precisaria de uma FAT de ~800 MB só pra indexação. A abordagem por
i-node só carrega os ponteiros do arquivo que está sendo acessado, não do
disco inteiro.

**12. Como funcionam as entradas de diretório, e como `.` e `..` são
implementados?**
Cada entrada tem 32 bytes fixos: 28 para o nome + 4 para o número do
i-node (`DIRENT_FORMAT` em `fs/constants.py:47-51`), então cabem 64
entradas por bloco de 2048 B. `.` e `..` são entradas **reais**, gravadas
no próprio diretório quando ele é criado (`add_dir_entry(num, ".", num)` e
`add_dir_entry(num, "..", parent)` em `mkdir()`, `fs/filesystem.py:842-844`)
— não são um caso especial tratado à parte na hora de listar/navegar.

**13. O que acontece se o disco (ou os i-nodes) ficarem cheios no meio de
uma operação, por exemplo escrevendo um arquivo grande?**
A alocação é "tudo ou nada": `_grow()` calcula quantos blocos/i-nodes
extras são necessários, confere se existe saldo livre **antes** de
alocar qualquer coisa e, se faltar no meio do processo, desfaz (libera) o
que já tinha sido alocado e levanta erro — o arquivo/diretório fica exatamente
como estava antes, sem blocos ou i-nodes órfãos (`fs/filesystem.py:296-341`).
Testamos isso esgotando os 8192 i-nodes de propósito (Seção 11 do roteiro):
o sistema recusa cada operação nova com uma mensagem clara, sem travar.

**14. Como o `find_free()` do bitmap evita ficar lento à medida que o disco
enche?**
Guarda um cursor (`self._cursor`) com a última posição livre encontrada,
então a busca não recomeça do zero a cada alocação — sem isso, escrever um
arquivo grande bloco a bloco degradaria para O(n²) (`fs/bitmap.py:33-45`).

---

## Camada 3 — Diretórios, links e navegação (provável)

**15. Qual a diferença entre link simbólico (soft) e link físico (hard)? O
que vocês implementaram?**
Hard link é uma segunda entrada de diretório apontando pro **mesmo**
i-node (existe um contador de referências; o arquivo só é liberado quando
a contagem chega a zero). Soft link (`ln -s`) é um i-node próprio, de tipo
diferente, cujo **conteúdo** é o caminho de texto do alvo — é resolvido
seguindo esse caminho toda vez. O enunciado pede `ln -s`, então
implementamos apenas soft link: `TYPE_SYMLINK` em `fs/filesystem.py:804-824`,
onde o "conteúdo" do link é gravado com `write_data()` normalmente, só que
o dado é o caminho, não bytes de um arquivo comum.

**16. Como é evitado um loop infinito de links simbólicos (ex.: `a` aponta
pra `b`, `b` aponta pra `a`)?**
`resolve()` recebe um contador de profundidade (`_depth`) que aumenta a
cada link seguido e aborta com erro depois de 20 níveis
(`fs/filesystem.py:592-596`).

**17. `rm` num link simbólico apaga o arquivo apontado?**
Não — `rm` opera sobre a entrada de diretório e o i-node do **link em si**
(que nunca segue o alvo para remoção), então o arquivo original continua
intacto. Testado na Seção 4/7 do roteiro.

**18. Qual a diferença entre `cp` e `mv` em termos de i-nodes/blocos
usados?**
`cp` lê todo o conteúdo do arquivo original e escreve num i-node **novo**,
com blocos próprios — é uma cópia de verdade, editar uma não afeta a outra
(`fs/filesystem.py:749-765`). `mv` não toca nos dados: só remove a entrada
de diretório antiga, cria uma nova apontando pro **mesmo** i-node, e
atualiza o nome gravado no i-node; se o diretório mudar de pai, também
atualiza a entrada `..` do item movido (`fs/filesystem.py:767-802`).

**19. Por que `rmdir` só funciona em diretório vazio, e como isso é
checado?**
Por definição de "vazio": se apagássemos um diretório com conteúdo,
teríamos i-nodes/blocos órfãos sem nenhuma entrada de diretório
referenciando-os — dados perdidos e sem forma de recuperar espaço depois. A
checagem lista as entradas do diretório ignorando `.`/`..`
(`fs/filesystem.py:852-868`); se sobrar qualquer coisa, recusa com erro.

**20. O que acontece se eu tentar mover um diretório para dentro dele
mesmo (ex.: `mv a a/b/dentro`)?**
É bloqueado explicitamente: antes de mover, verifica se o destino é o
próprio diretório ou um descendente dele (`_is_ancestor()`,
`fs/filesystem.py:671-682`, chamada em `mv()`), senão a árvore ficaria
inacessível (um diretório sendo pai de si mesmo).

---

## Camada 4 — Decisões de projeto e limitações conscientes (possível,
perguntas mais "de entendimento")

**21. O i-node guarda permissões de leitura/escrita/execução (dono e
outros), mas alguma operação verifica isso?**
Não. O campo existe e é exibido (`ls`/`stat` mostram `drwxr-x` etc., ver
`perm_string()` em `fs/filesystem.py:574-581`), atendendo ao requisito de
**estrutura** do i-node, mas nenhuma operação nega acesso com base nele —
essa é uma decisão de escopo, documentada no `README.md`: o controle de
acesso de verdade (múltiplos usuários, `chmod`) fica para o trabalho de
Segurança do próximo bimestre. *(Se o professor perguntar isso, é bom
confirmar que ele já validou esse plano com vocês, se aplicável.)*

**22. O sistema aguenta múltiplos processos acessando o mesmo disco ao
mesmo tempo (concorrência)?**
Não — é uma limitação assumida: o sistema mantém em memória um cache do
conteúdo de diretórios já lidos nesta sessão (`_dir_cache`,
`fs/filesystem.py:55-63`) partindo do princípio de que só esse processo
mexe no arquivo de disco. Se dois processos abrissem o mesmo `disco.img`
ao mesmo tempo, um não veria as mudanças do outro e poderia corromper o
bitmap/tabela de i-nodes por escritas concorrentes sem nenhum tipo de
lock. O slide de introdução cita concorrência como requisito de sistemas de
arquivos "de verdade"; aqui ficou fora de escopo (uso de um único processo
por vez).

**23. Se o processo travar no meio de uma escrita (queda de energia, por
exemplo), o disco fica consistente?**
Parcialmente: cada `write_block` é uma escrita individual no arquivo, e o
`fsync` acontece ao final de cada **comando** do shell (não de cada
`write_block`), então uma operação que mexe em vários blocos (ex.: `_grow`
alocando 3 blocos novos) pode, em teoria, ficar com só parte gravada se a
energia cair no meio. Não há journaling nem transações atômicas de
verdade — é uma simplificação aceitável para o escopo do trabalho, mas
importante saber explicar essa limitação se perguntarem.

**24. Qual o número máximo de arquivos/diretórios que o sistema
suporta, e por quê?**
8192 (`NUM_INODES` em `fs/constants.py:30`), porque a tabela de i-nodes
tem tamanho fixo reservado no mkfs. Escolhido para caber numa quantidade
"redonda" de blocos (1 MiB exatos = 512 blocos de 2048 B) sem desperdiçar
espaço nem limitar demais os testes. Isso também significa que i-nodes de
continuação (pergunta 10) saem dessa mesma tabela — um arquivo muito
grande "gasta" i-nodes extras, não só blocos.

**25. Por que o nome de arquivo/diretório tem um limite de tamanho (27
bytes)? De onde vem esse número?**
Vem do tamanho fixo da entrada de diretório: 32 bytes totais, sendo 4 para
o número do i-node, sobrando 28 para o nome (`DIRENT_FORMAT`,
`fs/constants.py:47-51`); usamos 27 (não os 28 inteiros) pra garantir que a
string sempre tenha pelo menos 1 byte de folga/terminador ao ser codificada
em UTF-8, já que um caractere acentuado pode ocupar mais de 1 byte.

**26. Onde ficam armazenados os atributos do arquivo: no diretório ou no
i-node? Por que essa escolha (comparando com o que foi visto em aula)?**
No i-node — como o slide mostra, é a abordagem UNIX (no Windows os
atributos ficam na própria entrada do diretório). A vantagem é que mover
ou renomear um arquivo não exige tocar nos atributos, só na entrada de
diretório (nome → número do i-node); e um mesmo i-node pode, em teoria, ser
referenciado por mais de uma entrada (hard link) sem duplicar os
atributos.

---

## Camada 5 — Perguntas de teoria geral (podem ser feitas para qualquer
grupo, sem nem olhar o código)

**27. Qual a diferença entre superbloco e i-node?**
Superbloco guarda informações **do sistema de arquivos inteiro**
(tamanho do bloco, total de blocos/i-nodes, onde cada região começa,
contadores de livres — `fs/structs.py:32-85`); i-node guarda informações
**de um arquivo/diretório específico**.

**28. Por que dividir o disco em blocos de tamanho fixo (2048 B) em vez de
alocar exatamente o tanto de bytes que cada arquivo precisa?**
Blocos de tamanho fixo simplificam a alocação/liberação (basta um bit por
bloco no bitmap) e o endereçamento (ponteiro = número do bloco, tamanho
sempre igual); o custo é desperdiçar, em média, parte do último bloco de
cada arquivo (fragmentação interna) — trade-off clássico visto em aula.

**29. O que é um MBR, e o projeto de vocês tem algo parecido?**
MBR é o setor 0 de um disco **particionado**, usado pra boot e pra guardar
a tabela de partições. Nosso "disco" é um único arquivo sem partições — o
bloco 0 já é diretamente o superbloco do nosso sistema de arquivos, então
não existe (nem faz sentido existir) um MBR aqui.

**30. Um arquivo, pro sistema operacional, é uma sequência de bytes com
estrutura própria (como um banco de dados) ou só bytes "burros"?**
Como em UNIX/Windows (mencionado no slide), o sistema de arquivos não sabe
nada sobre o conteúdo — é só uma sequência de bytes. Toda a interpretação
(texto, imagem etc.) é responsabilidade de quem lê o arquivo, não do
sistema de arquivos. No nosso caso, `read_data()`/`write_data()`
(`fs/filesystem.py:386-423`) trabalham só com `bytes`, sem qualquer
parsing de conteúdo.

---

## Dicas rápidas para a apresentação

- Se travarem em alguma pergunta, é mais seguro dizer "essa parte específica
  ficou fora do escopo por causa de X" (ex.: permissões, concorrência,
  atomicidade total) do que inventar uma resposta — o `README.md` já lista
  essas limitações de forma explícita, então admitir a limitação é
  consistente com o que está documentado.
- Antes da apresentação, rodem o `ROTEIRO_DE_TESTES.md` do início ao fim
  pelo menos uma vez ao vivo — várias das perguntas acima (persistência,
  i-node de continuação, disco cheio) ficam muito mais fáceis de explicar
  depois de ver acontecendo na tela.
