# Sistema de Arquivos baseado em i-nodes

Implementação em Python (sem uso de JSON/pickle — apenas o módulo `struct`
da biblioteca padrão) de um sistema de arquivos baseado em i-nodes, para a
disciplina de Sistemas Operacionais.

O "disco" é um único arquivo binário (`disco.img`) de **exatamente 128 MB**,
que guarda tanto os metadados (superbloco, bitmaps, tabela de i-nodes)
quanto os dados dos arquivos e diretórios. O sistema é persistente: os dados
sobrevivem ao encerramento do processo e são recarregados na próxima
execução.

## Enunciado do trabalho

Resumo dos requisitos pedidos (de acordo com o ava):

- Disco rígido de **128 MB**, com blocos de armazenamento de **2048 B**.
- Cada **i-node** deve ter: nome do arquivo/diretório, criador, dono,
  tamanho, data de criação, data de modificação, permissões de acesso
  (dono e outros usuários — leitura, escrita, execução), ponteiros para
  blocos, e ponteiro para um eventual outro i-node.
- Parte do disco é usada para gerenciamento (controle de blocos/i-nodes
  livres/ocupados e os i-nodes em si) — o restante é a área de dados.
- **Operações sobre arquivos:** criar (`touch`), remover (`rm`), criar já
  com conteúdo (`echo "..." > arquivo`), adicionar conteúdo/criar se não
  existir (`echo "..." >> arquivo`), ler (`cat`), copiar (`cp`),
  renomear/mover (`mv`), criar link entre arquivos (`ln -s`).
- **Operações sobre diretórios:** criar (`mkdir`), remover só se vazio
  (`rmdir`), listar (`ls`), trocar de diretório (`cd`, com `.` e `..`),
  renomear/mover (`mv`), criar link (`ln -s`).
- O sistema de arquivos deve ser **persistente** (sobrevive ao encerramento
  do processo) e todos os comandos devem funcionar com **caminhos
  absolutos e relativos**.
- Deve ser implementado em **Python**, sem usar JSON para nada, com i-node
  de tamanho fixo e potência de 2, e o disco inteiro (dados + gerenciamento)
  não pode passar de 128 MB.
- Critérios de avaliação: (1) as operações funcionam corretamente; (2) há
  persistência de dados; (3) o limite de 128 MB é respeitado e bem
  aproveitado.

**Fora do escopo desta entrega:** o enunciado lista "permissões de acesso"
como campo do i-node, mas não pede nenhuma operação de controle de acesso
(Então por enquanto, não há `chmod`, troca de usuário, 
nem negação de operação por permissão na lista acima). Por conta disso, essa parte (controle de
acesso de verdade, com múltiplos usuários/grupos) será tratada em um
trabalho futuro de Segurança no 4 bim. Por isso, aqui o i-node **guarda** o
campo de permissões (estrutura correta), mas nenhuma operação o **verifica**
— ver a seção "Permissões" mais abaixo.

## Como executar

```bash
python main.py
```

Por padrão o disco é criado/aberto como `disco.img` na raiz do projeto. Para
usar outro arquivo, ou definir o usuário que aparecerá como criador/dono
dos arquivos criados nesta sessão:

```bash
python main.py --disk meu_disco.img --user sei_la
```

Na primeira execução o disco de 128 MB é criado e formatado (`mkfs`). Nas
execuções seguintes, o mesmo arquivo é montado e todo o conteúdo anterior
continua disponível.

## Como testar

O arquivo [`ROTEIRO_DE_TESTES.md`](ROTEIRO_DE_TESTES.md) traz um roteiro
completo, comando a comando, cobrindo todas as operações pedidas (arquivos,
diretórios, links, caminhos absolutos/relativos, erros esperados e o teste
de persistência reabrindo o disco). Use-o tanto para testar quanto como
guia na apresentação.

## Comandos suportados

### Arquivos
| Comando | Efeito |
|---|---|
| `touch arquivo` | cria arquivo vazio |
| `rm arquivo` | remove arquivo |
| `echo "conteúdo" > arquivo` | cria/sobrescreve o arquivo com o conteúdo |
| `echo "conteúdo" >> arquivo` | acrescenta conteúdo ao final (cria se não existir) |
| `cat arquivo` | mostra o conteúdo do arquivo |
| `cp arquivo1 arquivo2` | copia arquivo |
| `mv arquivo1 arquivo2` | renomeia/move arquivo |
| `ln -s arquivoOriginal link` | cria link simbólico (soft link) |

### Diretórios
| Comando | Efeito |
|---|---|
| `mkdir diretorio` | cria diretório |
| `rmdir diretorio` | remove diretório (somente se vazio) |
| `ls [diretorio]` | lista conteúdo do diretório |
| `cd diretorio` | troca o diretório atual (`.` e `..` suportados) |
| `mv diretorio1 diretorio2` | renomeia/move diretório |
| `ln -s original link` | também funciona apontando para diretórios |

Todos os comandos aceitam caminhos **absolutos** (`/a/b/c`) e **relativos**
(`a/b/c`, `./a`, `../a`).

### Extras (para demonstração de persistência/uso de disco)
`pwd`, `stat <caminho>`, `df` (ou `info`), `reset`, `help`, `exit`.

## Layout físico do disco

Disco de 128 MB, dividido em blocos de **2048 B**, resultando em
**65536 blocos**. O layout (calculado em `fs/constants.py`, com `assert`s
que validam as contas) é:

| Região | Blocos | Tamanho | Conteúdo |
|---|---|---|---|
| Superbloco | 1 (bloco 0) | 2 KB | metadados globais do sistema de arquivos |
| Bitmap de i-nodes | 1 (bloco 1) | 2 KB | controla os 8192 i-nodes (livre/ocupado) |
| Bitmap de blocos | 4 (blocos 2-5) | 8 KB | controla os 65536 blocos (livre/ocupado) |
| Tabela de i-nodes | 512 (blocos 6-517) | 1 MB | 8192 i-nodes × 128 B cada |
| **Área de dados** | 65018 (blocos 518-65535) | **~127,0 MB** | conteúdo de arquivos/diretórios |

**Overhead de gerenciamento: 518 blocos = 1.036.576 B ≈ 0,77% do disco.**
Os outros **99,23% (≈127 MB)** ficam disponíveis para dados — ou seja, o
sistema usa o disco de forma eficiente sem estourar os 128 MB (a soma de
todas as regiões é exatamente `65536 × 2048 = 134.217.728 B = 128 MB`).

O número de i-nodes (8192) foi escolhido para permitir uma quantidade
generosa de arquivos/diretórios (bem acima do necessário para qualquer
demonstração) gastando apenas 1 MB de tabela de i-nodes.

## Estrutura do i-node

I-node de tamanho **fixo e potência de 2: 128 bytes** (exigência do
enunciado), contendo exatamente os campos pedidos:

| Campo | Bytes | Descrição |
|---|---|---|
| `used` | 1 | i-node está em uso? |
| `type` | 1 | 0 = arquivo, 1 = diretório, 2 = link simbólico |
| `perm` | 1 | permissões: 3 bits dono (rwx) + 3 bits outros (rwx) |
| (reservado) | 1 | alinhamento |
| `name` | 32 | nome do arquivo/diretório |
| `creator` | 16 | criador |
| `owner` | 16 | dono |
| `size` | 8 | tamanho em bytes |
| `created_at` | 8 | data de criação (timestamp) |
| `modified_at` | 8 | data de modificação (timestamp) |
| `pointers[8]` | 32 | 8 ponteiros diretos para blocos de dados (4 B cada) |
| `next_inode` | 4 | ponteiro para um eventual **outro i-node** de continuação |
| **Total** | **128** | |

Com blocos de 2048 B e 8 ponteiros diretos, cada i-node referencia até
**16 KB** de dados diretamente. Se o arquivo crescer além disso, um **novo
i-node é alocado só para servir de continuação** (mais 8 ponteiros, e assim
por diante, encadeando via `next_inode`) — exatamente o mecanismo descrito
no enunciado ("apontador para eventual outro i-node"), em vez do clássico
bloco de índices indiretos. Esse encadeamento foi testado com um arquivo de
20.480 B (10 blocos), que corretamente aloca um i-node de continuação com 2
ponteiros extras, e é desfeito automaticamente (i-node de continuação e
blocos liberados) quando o arquivo é reduzido ou removido.

## Diretórios

O conteúdo de um diretório é uma sequência de **entradas de 32 bytes**
(nome de até 28 B + número do i-node, 4 B), armazenada nos blocos de dados
do próprio i-node do diretório (usando o mesmo mecanismo de ponteiros
diretos/continuação dos arquivos). Cada bloco de 2048 B comporta exatamente
64 entradas. Todo diretório é criado com as entradas especiais `.` (ele
mesmo) e `..` (pai) — inclusive a raiz, cujo `..` aponta para si mesma.

## Links simbólicos

`ln -s original link` cria um i-node do tipo *symlink* cujo "conteúdo" (via
o mesmo mecanismo de blocos de dados) é o caminho de destino (absoluto ou
relativo), sem exigir que o destino exista. Operações de leitura (`cat`,
`cp`, `cd`, `ls dir`, resolução de caminho) seguem o link automaticamente;
operações que atuam sobre o próprio link (`rm`, `mv`) não o seguem. Loops de
links são detectados e rejeitados. Apenas soft link é implementado (hard
link não é exigido pelo enunciado).

## Permissões

Cada i-node guarda `creator`, `owner` e um byte de permissões (`rwx` do
dono + `rwx` de outros, sem grupo), exatamente como pedido na estrutura do
i-node do enunciado. O `creator`/`owner` são preenchidos com o usuário atual
da sessão (por padrão, o usuário do sistema operacional, via
`getpass.getuser()`, ou `--user` na linha de comando) sempre que um
arquivo/diretório/link é criado, e as permissões padrão aplicadas são
`rw-r--` para arquivos e `rwxr-x` para diretórios. O comando `stat` (e a
listagem do `ls`) mostram esses campos.

**Nenhuma operação verifica ou aplica essas permissões** — não existe
usuário "atual" que possa ser trocado nem uma operação que seja negada por
falta de permissão. Isso é proposital: o professor indicou que o controle
de acesso de verdade (múltiplos usuários, grupos, algo como `sudo`) é o
tema do trabalho de **Segurança de SO** do último bimestre, então essa
lógica fica fora do escopo desta entrega. A versão anterior deste projeto,
que já tinha esse controle de acesso implementado e funcional (com `su`
para trocar de usuário simulado e checagem de leitura/escrita/execução em
toda operação), foi preservada na branch `com-permissoes` do git, para ser
reaproveitada quando esse próximo trabalho for feito.

## Persistência

Todas as escritas (superbloco, bitmaps, i-nodes, blocos de dados) são feitas
diretamente na imagem de disco a cada operação, e o shell força
`flush()`/`fsync()` após cada comando digitado. Ou seja, mesmo que o
processo seja encerrado logo após um comando, o estado já está gravado
fisicamente no arquivo `disco.img`. Ao reiniciar (`python main.py`), o
superbloco é lido, o *magic number* validado, e os bitmaps recarregados —
todo o conteúdo criado anteriormente continua acessível.

## Limitações conhecidas (escopo definido pelo enunciado)

- Apenas soft link (não implementa hard link, conforme permitido).
- Nomes de arquivo/diretório limitados a 27 caracteres (cabem com folga nos
  campos de 28/32 bytes do i-node e da entrada de diretório).
- Não há acesso concorrente entre múltiplos processos ao mesmo `disco.img`
  (fora do escopo das operações pedidas).
- `cp` opera apenas sobre arquivos, como especificado.
