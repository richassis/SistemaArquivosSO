"""
Constantes e cálculo do layout físico do disco.

O "disco" é um único arquivo binário de exatamente 128 MiB. Ele é dividido em
blocos de 2048 B (2 KiB). O layout, em blocos, é:

    [0]         Superbloco
    [1]         Bitmap de i-nodes
    [2..5]      Bitmap de blocos
    [6..517]    Tabela de i-nodes
    [518..65535] Região de dados

Todos os números abaixo são derivados matematicamente dos requisitos do
trabalho (disco de 128 MB, blocos de 2048 B, i-node de tamanho fixo e
potência de 2), e não são "chutados": ver README.md para a justificativa
de cada valor e quanto do disco é gasto com metadados.
"""

import struct

# ---------------------------------------------------------------------------
# Parâmetros fixos exigidos pelo enunciado
# ---------------------------------------------------------------------------
DISK_SIZE = 128 * 1024 * 1024          # 128 MB exatos
BLOCK_SIZE = 2048                      # 2048 B por bloco
TOTAL_BLOCKS = DISK_SIZE // BLOCK_SIZE  # 65536 blocos
assert TOTAL_BLOCKS * BLOCK_SIZE == DISK_SIZE

# ---------------------------------------------------------------------------
# I-node: tamanho fixo, potência de 2 (128 B)
# ---------------------------------------------------------------------------
DIRECT_POINTERS = 8   # ponteiros diretos para blocos de dados por i-node
INODE_FORMAT = "<BBBB32s16s16sQdd8Ii"
#                |||| |     |     |    |  |  |    |
#                |||| name  creat owner|  |  |    +-- next_inode (i, 4B)
#                |||| (32B) (16B) (16B)|  |  +------- 8 ponteiros diretos (8I, 32B)
#                |||| |     |     |    |  +---------- modified_at (d, 8B)
#                |||| |     |     |    +------------- created_at (d, 8B)
#                |||+-- reservado/alinhamento (1B)     size (Q, 8B)
#                ||+--- permissoes (1B)
#                |+---- tipo (1B)
#                +----- used (1B)
INODE_SIZE = struct.calcsize(INODE_FORMAT)
assert INODE_SIZE == 128, INODE_SIZE
assert (INODE_SIZE & (INODE_SIZE - 1)) == 0, "i-node precisa ter tamanho potencia de 2"

MAX_NAME_LEN = 27          # nome de arquivo/diretorio (cabe em name[32] e em dirent)
MAX_USER_LEN = 15          # criador/dono

# Quantidade de i-nodes suportados pelo sistema de arquivos.
NUM_INODES = 8192
INODE_TABLE_BYTES = NUM_INODES * INODE_SIZE
assert INODE_TABLE_BYTES % BLOCK_SIZE == 0
INODE_TABLE_BLOCKS = INODE_TABLE_BYTES // BLOCK_SIZE  # 512 blocos = 1 MiB

# ---------------------------------------------------------------------------
# Tipos de i-node
# ---------------------------------------------------------------------------
TYPE_FILE = 0
TYPE_DIR = 1
TYPE_SYMLINK = 2

# ---------------------------------------------------------------------------
# Permissoes: 6 bits (dono rwx | outros rwx) guardados em 1 byte do i-node
# ---------------------------------------------------------------------------
PERM_R, PERM_W, PERM_X = 0b100, 0b010, 0b001
DEFAULT_FILE_PERM = (PERM_R | PERM_W) << 3 | PERM_R              # rw-r--
DEFAULT_DIR_PERM = (PERM_R | PERM_W | PERM_X) << 3 | (PERM_R | PERM_X)  # rwxr-x
DEFAULT_SYMLINK_PERM = (PERM_R | PERM_W | PERM_X) << 3 | (PERM_R | PERM_W | PERM_X)  # rwxrwx

# ---------------------------------------------------------------------------
# Entrada de diretorio: nome (28B) + numero do i-node (4B) = 32B
# Blocos de 2048B guardam exatamente 64 entradas por bloco.
# ---------------------------------------------------------------------------
DIRENT_FORMAT = "<28sI"
DIRENT_SIZE = struct.calcsize(DIRENT_FORMAT)
assert DIRENT_SIZE == 32
ENTRIES_PER_BLOCK = BLOCK_SIZE // DIRENT_SIZE
assert ENTRIES_PER_BLOCK * DIRENT_SIZE == BLOCK_SIZE
EMPTY_ENTRY = 0xFFFFFFFF  # sentinela: slot de diretorio livre

# ---------------------------------------------------------------------------
# Superbloco (cabe folgado dentro de 1 bloco de 2048B)
# ---------------------------------------------------------------------------
SUPERBLOCK_MAGIC = b"SOFS"
SUPERBLOCK_FORMAT = "<4s11Id"
SUPERBLOCK_SIZE = struct.calcsize(SUPERBLOCK_FORMAT)
assert SUPERBLOCK_SIZE <= BLOCK_SIZE

# ---------------------------------------------------------------------------
# Layout em blocos (posições fixas, calculadas a partir do exposto acima)
# ---------------------------------------------------------------------------
SUPERBLOCK_START = 0
SUPERBLOCK_BLOCKS = 1

INODE_BITMAP_START = SUPERBLOCK_START + SUPERBLOCK_BLOCKS          # bloco 1
INODE_BITMAP_BYTES = (NUM_INODES + 7) // 8
INODE_BITMAP_BLOCKS = (INODE_BITMAP_BYTES + BLOCK_SIZE - 1) // BLOCK_SIZE  # 1

BLOCK_BITMAP_START = INODE_BITMAP_START + INODE_BITMAP_BLOCKS      # bloco 2
BLOCK_BITMAP_BYTES = (TOTAL_BLOCKS + 7) // 8
BLOCK_BITMAP_BLOCKS = (BLOCK_BITMAP_BYTES + BLOCK_SIZE - 1) // BLOCK_SIZE  # 4

INODE_TABLE_START = BLOCK_BITMAP_START + BLOCK_BITMAP_BLOCKS       # bloco 6
# INODE_TABLE_BLOCKS = 512, calculado acima              -> termina no bloco 517

DATA_START = INODE_TABLE_START + INODE_TABLE_BLOCKS                # bloco 518
DATA_BLOCKS = TOTAL_BLOCKS - DATA_START
assert DATA_BLOCKS > 0

ROOT_INODE = 0

RESERVED_BLOCKS = DATA_START  # blocos 0..DATA_START-1 sao sempre "usados"
