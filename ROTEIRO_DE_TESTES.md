# Roteiro de testes

Este roteiro serve para **qualquer pessoa** testar e explorar o sistema de
arquivos, mesmo sem conhecer o código antes. Cada seção traz os comandos
para colar (uma linha por comando, dá pra colar o bloco inteiro de uma vez)
e o que é **esperado** acontecer, para você conferir contra a saída real.

## Como rodar

```
python main.py                          # usa ./disco.img (cria se não existir)
python main.py --disk outro.img         # usa outro arquivo de disco
python main.py --user maria             # define o usuário (criador/dono dos arquivos)
```

Na primeira vez que um caminho de disco é usado, ele é criado do zero com
exatamente 128 MB e formatado (`mkfs`). Nas próximas vezes, o mesmo arquivo é
apenas montado e todo o conteúdo anterior continua lá.

> Recomendação: para seguir este roteiro do início, use um disco novo (ex.:
> `python main.py --disk teste.img`), para não misturar com o conteúdo que
> já possa existir em `disco.img`. Delete `teste.img` no final se não quiser
> mantê-lo.

Digite `help` a qualquer momento para ver a lista de comandos.

---

## 1. Diretório atual, `mkdir`, `ls`, `cd`, `pwd`

```
pwd
mkdir docs
mkdir docs/so
ls
cd docs
pwd
ls
```
**Esperado:** `pwd` inicial mostra `/`. Depois do primeiro `mkdir`, `ls` na
raiz mostra `docs` (tipo diretório, prefixo `d` na permissão). Depois do
`cd docs`, `pwd` mostra `/docs` e `ls` mostra `so`.

## 2. Arquivos: `touch`, `echo >`, `echo >>`, `cat`

```
touch a.txt
ls
echo "conteudo legal" > a.txt
cat a.txt
echo "mais uma linha" >> a.txt
cat a.txt
ls
```
**Esperado:** `touch` cria arquivo vazio (0 bytes). Primeiro `cat` mostra só
`conteudo legal`. Depois do `>>`, o `cat` mostra as duas linhas
(`conteudo legal` seguido de `mais uma linha`). `ls` mostra `a.txt` com 30
bytes (15 + 15, contando a quebra de linha de cada `echo`).

`echo` também funciona sem aspas e com `>`/`>>` colados no nome do arquivo
(sem espaço):
```
echo ola mundo > semaspas.txt
cat semaspas.txt
echo "colado">colado.txt
cat colado.txt
```
**Esperado:** `semaspas.txt` contém `ola mundo`; `colado.txt` contém
`colado`.

## 3. `cp` e `mv` (arquivos)

```
cp a.txt b.txt
cat b.txt
mv b.txt so/c.txt
ls so
ls
```
**Esperado:** `b.txt` é uma cópia **independente** de `a.txt` (mesmo
conteúdo, blocos próprios). Depois do `mv`, `b.txt` não existe mais em
`docs` e passa a existir como `docs/so/c.txt`.

```
mv a.txt a.txt
```
**Esperado:** erro `já existe` — `mv` não sobrescreve um destino existente
(nem quando origem e destino têm o mesmo nome).

## 4. Link simbólico (`ln -s`)

```
cd ..
ln -s /docs/a.txt link1
cat link1
stat link1
```
**Esperado:** `cat link1` mostra o mesmo conteúdo de `/docs/a.txt` (o link é
seguido automaticamente). `stat link1` mostra tipo "link simbólico", o
tamanho é o do **caminho de destino** (`/docs/a.txt`, 11 bytes), não o do
arquivo apontado, e usa 1 bloco.

Link simbólico também funciona apontando para diretório:
```
ln -s /docs linkdocs
ls linkdocs
cd linkdocs
pwd
cd /
```
**Esperado:** `ls linkdocs` mostra o conteúdo de `/docs`. `cd linkdocs`
segue o link e `pwd` mostra o caminho real (`/docs`).

Link "pendurado" (apontando para algo que não existe) é permitido de criar,
só falha ao tentar seguir:
```
ln -s /nao/existe quebrado
stat quebrado
cat quebrado
```
**Esperado:** `stat` funciona normalmente (mostra o link em si). `cat` dá
erro `arquivo ou diretório não encontrado`.

Ciclo de links é detectado (não trava o programa):
```
ln -s /ciclo_b ciclo_a
ln -s /ciclo_a ciclo_b
cat ciclo_a
```
**Esperado:** erro `loop de links simbólicos detectado`.

## 5. Caminhos absolutos e relativos, `.` e `..`

```
cd docs/so
pwd
cd ..
pwd
cd ../docs
pwd
cd ./so
pwd
cd /
pwd
```
**Esperado:** cada `pwd` reflete corretamente o caminho absoluto atual:
`/docs/so` → `/docs` → `/docs` (via relativo `../docs` a partir de `so`) →
`/docs/so` (via `./so`) → `/`.

## 6. Diretórios: `mv`, `rmdir` só funciona vazio

```
mkdir pastavazia
rmdir pastavazia
mkdir a
mkdir a/b
mv a a2
ls
cd a2/b
pwd
cd /
```
**Esperado:** `rmdir pastavazia` funciona silenciosamente (sem saída). Após
`mv a a2`, o diretório `a2/b` existe e `..` dentro dele aponta corretamente
para `a2` mesmo depois do rename (repare que `pwd` dentro de `a2/b` mostra
`/a2/b`, não `/a/b`).

```
rmdir docs
```
**Esperado:** **erro** `diretório não está vazio` — `docs` ainda contém
`a.txt` e `so/c.txt`. Esse erro é o comportamento correto, não um bug.

## 7. `rm`

```
rm docs/a.txt
rm link1
ls docs
```
**Esperado:** depois de remover `a.txt`, `ls docs` mostra `colado.txt`,
`semaspas.txt` e `so` (os outros arquivos criados no passo 2, que não foram
tocados). O link `link1` também é removido; o arquivo `docs/so/c.txt`
(cópia independente feita no passo 3) continua existindo normalmente.

## 8. Erros esperados (validação)

Estes comandos devem **falhar** com mensagem de erro clara — é o
comportamento correto, não uma falha do sistema:

```
mkdir a2
cat a2
rm a2
rmdir naoexiste
ln -s /a /b/c/d/link
cp a2 outracopia
cd nao_existe
mv nao_existe outro
touch nome_com_mais_de_27_bytes_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
```
- `mkdir a2` (se já existir): `já existe`
- `cat a2`: `é um diretório`
- `rm a2`: `é um diretório (use rmdir)`
- `rmdir naoexiste`: `diretório não encontrado`
- `ln -s /a /b/c/d/link` (caminho pai inexistente): `arquivo ou diretório
  não encontrado`
- `cp a2 outracopia` (origem é diretório): `cp só é suportado para
  arquivos`
- `cd nao_existe` / `mv nao_existe outro`: `não encontrado`
- nome de arquivo maior que 27 bytes em UTF-8: `nome muito longo`

## 9. Diagnóstico: `stat` e `df`

```
stat /
df
```
**Esperado:** `stat /` mostra o i-node raiz (i-node 0, tipo diretório).
`df` mostra o disco total de 128 MB, ~518 blocos (1 MB) gastos com
metadados, a área de dados (~127 MB) e quantos blocos/i-nodes estão em uso
até aqui.

## 10. Arquivo grande (exercita o i-node de continuação)

Os 8 ponteiros diretos de um i-node cobrem até 16 KB (2048 B × 8). Para
forçar o uso do "apontador para outro i-node" pedido no enunciado, basta
passar desse tamanho. No PowerShell/bash, gere e cole várias linhas de uma
vez em vez de digitar `echo >>` centenas de vezes manualmente. Exemplo em
bash (gera 300 linhas de `echo ... >> grande.txt`, suficiente para passar
de 16 KB, e cola tudo no `python main.py`):

```bash
{
  echo "touch grande.txt"
  for i in $(seq 1 300); do echo 'echo "0123456789012345678901234567890123456789012345678901234567890123" >> grande.txt'; done
  echo "stat grande.txt"
} | python main.py --disk teste.img
```

**Esperado:** o `stat` no final mostra mais de 21 mil bytes e **mais de 8
blocos usados** — ou seja, o i-node cabeça encheu os 8 ponteiros diretos e
o restante do arquivo passou a usar um **segundo i-node encadeado** via
`next_inode`, de forma totalmente transparente para quem usa o `cat`/`stat`.

## 11. Disco cheio / limite de i-nodes (opcional, mostra que falha com
elegância)

O sistema tem 8192 i-nodes no total. Para ver o comportamento quando eles
acabam (sem travar nem corromper o disco), crie um disco novo e tente criar
mais arquivos do que i-nodes disponíveis:

```bash
{
  for i in $(seq 1 8300); do echo "touch f$i.txt"; done
  echo "df"
} | python main.py --disk cheio_teste.img
```
**Esperado:** os primeiros ~8188 `touch` funcionam (o restante dos
i-nodes já está usado pela raiz e por `.`/`..`); a partir daí, cada `touch`
extra falha com `sem i-nodes livres (limite de arquivos/diretorios
atingido)`, sem interromper o shell. `df` no final mostra `8192/8192`
i-nodes usados. Apague `cheio_teste.img` depois (são só 128 MB, mas não
tem por que manter).

## 12. Persistência

Sem sair do shell ainda, confira o estado atual e depois saia:
```
ls docs
ls docs/so
cat docs/so/c.txt
df
exit
```
Agora rode `python main.py --disk teste.img` **de novo** (mesmo arquivo de
disco) e confira que tudo continua lá **sem repetir nenhum comando
anterior**:
```
ls docs
ls docs/so
cat docs/so/c.txt
df
```
**Esperado:** exatamente o mesmo estado de antes do `exit` — a estrutura
`docs/so/c.txt` com o conteúdo copiado, e o `df` reportando os mesmos
blocos/i-nodes usados. Isso comprova a persistência: o processo foi
encerrado e todo o conteúdo foi recuperado do arquivo de disco (nenhum
dado vive só em memória).

## 13. `reset` (cuidado: apaga tudo)

```
reset
```
**Esperado:** pede confirmação (`Digite 'sim' para confirmar`); se
confirmado, apaga e reformata o disco atual do zero. Só use se realmente
quiser recomeçar o disco de teste.

---

## Onde olhar no código, se quiser ir além do roteiro

- `fs/constants.py` — layout do disco (tamanhos, offsets de cada região) e
  os `assert`s que garantem que fecha em 128 MB.
- `fs/disk.py` — leitura/escrita de blocos fixos de 2048 B no arquivo de
  disco.
- `fs/bitmap.py` — controle de i-nodes/blocos livres e ocupados.
- `fs/structs.py` — (de)serialização binária do superbloco, i-node e
  entrada de diretório com `struct` (sem JSON/pickle).
- `fs/filesystem.py` — toda a lógica: alocação, cadeia de i-nodes,
  diretórios, resolução de caminho, links.
- `fs/shell.py` — o REPL que expõe os comandos usados neste roteiro.
