# Roteiro de testes manuais

Este roteiro serve para testar (e para apresentar) o sistema de arquivos de
forma guiada, cobrindo todas as operações exigidas no trabalho. Rode
`python main.py` e vá colando os blocos de comando abaixo no prompt — cada
linha é um comando; pode colar o bloco inteiro de uma vez.

Cada seção traz o que é **esperado** acontecer, para você conferir contra a
saída real.

## 1. Diretório atual

```
pwd
mkdir docs
mkdir docs/so
ls
cd docs
pwd
```
**Esperado:** `pwd` inicial mostra `/`. `ls` na raiz mostra a entrada `docs`
(tipo diretório). Depois do `cd docs`, `pwd` mostra `/docs`.

## 2. Arquivos: touch, echo `>`, echo `>>`, cat

```
touch a.txt
echo "conteudo legal" > a.txt
cat a.txt
echo "mais uma linha" >> a.txt
cat a.txt
ls
```
**Esperado:** primeiro `cat` mostra só `conteudo legal`. Depois do `>>`, o
`cat` mostra as duas linhas (`conteudo legal` seguido de `mais uma linha`).
`ls` mostra `a.txt` com 30 bytes.

## 3. cp e mv

```
cp a.txt b.txt
cat b.txt
mv b.txt so/c.txt
ls so
ls
```
**Esperado:** `b.txt` é uma cópia independente de `a.txt` (mesmo conteúdo).
Depois do `mv`, `b.txt` não existe mais em `docs` e passa a existir como
`docs/so/c.txt`.

## 4. Link simbólico (`ln -s`)

```
cd ..
ln -s /docs/a.txt link1
cat link1
stat link1
```
**Esperado:** `cat link1` mostra o mesmo conteúdo de `/docs/a.txt` (o link
é seguido automaticamente). `stat link1` mostra tipo "link simbólico",
tamanho 11 bytes (tamanho da string `/docs/a.txt`) e 1 bloco usado.

## 5. Caminhos absolutos e relativos, `.` e `..`

```
cd docs/so
pwd
cd ..
pwd
cd ../docs
pwd
cd /
pwd
```
**Esperado:** cada `pwd` reflete corretamente o caminho absoluto atual:
`/docs/so` → `/docs` → `/docs` (via relativo `../docs` a partir de `so`) →
`/`.

## 6. rmdir só funciona vazio

```
mkdir vazio
rmdir vazio
rmdir docs
```
**Esperado:** `rmdir vazio` funciona silenciosamente (sem saída). Já
`rmdir docs` **deve dar erro** ("diretório não está vazio"), pois `docs`
ainda contém `a.txt` e `so/c.txt` — esse erro é o comportamento correto,
não um bug.

## 7. rm

```
rm docs/a.txt
rm link1
ls docs
```
**Esperado:** depois de remover `a.txt`, `ls docs` mostra só `so`. O link
`link1` também é removido (o arquivo `so/c.txt`, que é uma cópia
independente, continua existindo).

## 8. Diagnóstico: `stat` e `df`

```
stat /
df
```
**Esperado:** `stat /` mostra o i-node raiz (i-node 0, tipo diretório).
`df` mostra o disco total de 128MB, os ~518 blocos (1MB) gastos com
metadados, e a área de dados (~127MB) com a quantidade de blocos/i-nodes
usados até aqui.

## 9. Sair e testar persistência

```
exit
```
Depois disso, rode `python main.py` de novo (mesmo `disco.img`) e confira
que tudo continua lá **sem repetir os comandos acima**:

```
ls docs
ls docs/so
cat docs/so/c.txt
df
```
**Esperado:** exatamente o mesmo estado de antes do `exit` — a estrutura
`docs/so/c.txt` com o conteúdo copiado, e o `df` reportando os mesmos
blocos/i-nodes usados. Isso comprova que o disco é persistente: o processo
foi encerrado e todo o conteúdo foi recuperado do arquivo `disco.img`.

## 10. Arquivo grande (exercita o i-node de continuação)

Os 8 ponteiros diretos de um i-node cobrem até 16 KB. Para forçar o uso do
"apontador para outro i-node", acrescente conteúdo várias vezes:

```
touch grande.txt
echo "0123456789012345678901234567890123456789012345678901234567890123" > grande.txt
```
Repita o comando `echo "..." >> grande.txt` (com qualquer texto) umas 300
vezes, ou rode o mesmo `echo ... >>` dentro de um laço do seu terminal, até
passar de 16.384 bytes. Depois:

```
stat grande.txt
```
**Esperado:** o i-node cabeça (`pointers`) fica cheio (8 blocos) e o
arquivo passa a usar um **segundo i-node encadeado** via `next_inode` para
os blocos restantes — o `blocos usados` em `stat` mostra mais de 8 blocos.
Isso já foi validado automaticamente (ver seção de testes automatizados no
`README.md`), então esse passo é só para você visualizar o comportamento
ao vivo, se quiser.

## Erros esperados (para mostrar que a validação funciona)

Estes comandos devem **falhar** com uma mensagem de erro clara — isso é o
comportamento correto, não uma falha do sistema:

```
mkdir docs
cat docs
rm docs
rmdir naoexiste
ln -s /a /b/c/d/link
```
- `mkdir docs` (se `docs` já existir): "já existe"
- `cat docs`: "é um diretório"
- `rm docs`: "é um diretório (use rmdir)"
- `rmdir naoexiste`: "diretório não encontrado"
- `ln -s /a /b/c/d/link` (caminho pai inexistente): "arquivo ou diretório
  não encontrado"
