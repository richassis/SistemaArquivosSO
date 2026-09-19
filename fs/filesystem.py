# Logica do sistema de arquivos: alocacao de blocos/i-nodes, leitura e
# escrita de conteudo, diretorios, links simbolicos e resolucao de
# caminhos absolutos/relativos.
#
# Sobre permissoes: o i-node guarda o campo (dono/outros - rwx), que é
# exigido pela estrutura do enunciado, mas nenhuma operacao aqui verifica
# isso. O controle de acesso em si fica pro trabalho de Seguranca de SO do
# proximo bimestre (ver README).

from __future__ import annotations

import time
from typing import List, Optional, Tuple

from fs.bitmap import Bitmap
from fs.constants import (
    BLOCK_BITMAP_BLOCKS,
    BLOCK_BITMAP_START,
    BLOCK_SIZE,
    DATA_BLOCKS,
    DATA_START,
    DEFAULT_DIR_PERM,
    DEFAULT_FILE_PERM,
    DEFAULT_SYMLINK_PERM,
    DIRECT_POINTERS,
    DIRENT_SIZE,
    EMPTY_ENTRY,
    ENTRIES_PER_BLOCK,
    INODE_BITMAP_BLOCKS,
    INODE_BITMAP_START,
    INODE_SIZE,
    INODE_TABLE_START,
    MAX_NAME_LEN,
    NUM_INODES,
    RESERVED_BLOCKS,
    ROOT_INODE,
    TOTAL_BLOCKS,
    TYPE_DIR,
    TYPE_FILE,
    TYPE_SYMLINK,
)
from fs.disk import Disk
from fs.structs import DirEntry, Inode, SuperBlock


class FSError(Exception):
    """Erro de operacao do sistema de arquivos (mostrado ao usuario no shell)."""


class FileSystem:
    def __init__(self, path: str, current_user: str):
        self.path = path
        self.current_user = current_user

        if not Disk.exists(path):
            Disk.create(path)
            self.disk = Disk(path)
            self._mkfs()
        else:
            self.disk = Disk(path)
            self._mount()

        self.cwd_inode = self.sb.root_inode

    def _mkfs(self) -> None:
        self.sb = SuperBlock(
            block_size=BLOCK_SIZE,
            total_blocks=TOTAL_BLOCKS,
            num_inodes=NUM_INODES,
            inode_size=INODE_SIZE,
            inode_bitmap_start=INODE_BITMAP_START,
            block_bitmap_start=BLOCK_BITMAP_START,
            inode_table_start=INODE_TABLE_START,
            data_start=DATA_START,
            root_inode=ROOT_INODE,
            free_blocks=DATA_BLOCKS,
            free_inodes=NUM_INODES,
        )

        self.inode_bitmap = Bitmap(bytearray(INODE_BITMAP_BLOCKS * BLOCK_SIZE), NUM_INODES)
        self.block_bitmap = Bitmap(bytearray(BLOCK_BITMAP_BLOCKS * BLOCK_SIZE), TOTAL_BLOCKS)
        for b in range(RESERVED_BLOCKS):
            self.block_bitmap.set(b, True)

        # zera toda a tabela de i-nodes
        blank_inode_block = bytes(BLOCK_SIZE)
        for b in range(INODE_TABLE_START, INODE_TABLE_START + (NUM_INODES * INODE_SIZE) // BLOCK_SIZE):
            self.disk.write_block(b, blank_inode_block)

        self._save_superblock()
        self._save_inode_bitmap()
        self._save_block_bitmap()

        # cria o diretorio raiz (i-node 0)
        root_num = self.alloc_inode()
        assert root_num == ROOT_INODE
        now = time.time()
        root = Inode(
            used=1, type=TYPE_DIR, perm=DEFAULT_DIR_PERM,
            name="/", creator=self.current_user, owner=self.current_user,
            size=0, created_at=now, modified_at=now,
        )
        self.write_inode(root_num, root)
        self.add_dir_entry(root_num, ".", root_num, _validate=False)
        self.add_dir_entry(root_num, "..", root_num, _validate=False)
        self.disk.flush()

    def _mount(self) -> None:
        sb_block = self.disk.read_block(0)
        try:
            self.sb = SuperBlock.unpack(sb_block)
        except ValueError as exc:
            raise FSError(f"imagem de disco invalida ou corrompida: {exc}") from exc

        ib = bytearray()
        for i in range(INODE_BITMAP_BLOCKS):
            ib += self.disk.read_block(self.sb.inode_bitmap_start + i)
        self.inode_bitmap = Bitmap(ib, self.sb.num_inodes)

        bb = bytearray()
        for i in range(BLOCK_BITMAP_BLOCKS):
            bb += self.disk.read_block(self.sb.block_bitmap_start + i)
        self.block_bitmap = Bitmap(bb, self.sb.total_blocks)

    def _save_superblock(self) -> None:
        raw = self.sb.pack()
        raw = raw + b"\x00" * (BLOCK_SIZE - len(raw))
        self.disk.write_block(0, raw)

    def _save_inode_bitmap(self) -> None:
        data = bytes(self.inode_bitmap.data)
        for i in range(INODE_BITMAP_BLOCKS):
            chunk = data[i * BLOCK_SIZE:(i + 1) * BLOCK_SIZE]
            self.disk.write_block(self.sb.inode_bitmap_start + i, chunk)

    def _save_block_bitmap(self) -> None:
        data = bytes(self.block_bitmap.data)
        for i in range(BLOCK_BITMAP_BLOCKS):
            chunk = data[i * BLOCK_SIZE:(i + 1) * BLOCK_SIZE]
            self.disk.write_block(self.sb.block_bitmap_start + i, chunk)

    def close(self) -> None:
        self.disk.close()

    def flush(self) -> None:
        self.disk.flush()

    # aloca/libera i-nodes e blocos usando os bitmaps
    def alloc_inode(self) -> int:
        idx = self.inode_bitmap.find_free()
        if idx is None:
            raise FSError("sem i-nodes livres (limite de arquivos/diretorios atingido)")
        self.inode_bitmap.set(idx, True)
        self.sb.free_inodes -= 1
        self._save_inode_bitmap()
        self._save_superblock()
        return idx

    def free_inode(self, num: int) -> None:
        self.inode_bitmap.set(num, False)
        self.sb.free_inodes += 1
        self._save_inode_bitmap()
        self._save_superblock()
        self.write_inode(num, Inode())

    def alloc_block(self) -> int:
        idx = self.block_bitmap.find_free(start=DATA_START)
        if idx is None:
            raise FSError("disco cheio: sem blocos de dados livres")
        self.block_bitmap.set(idx, True)
        self.sb.free_blocks -= 1
        self._save_block_bitmap()
        self._save_superblock()
        return idx

    def free_block(self, num: int) -> None:
        if num < DATA_START:
            return
        self.block_bitmap.set(num, False)
        self.sb.free_blocks += 1
        self._save_block_bitmap()
        self._save_superblock()

    def _inode_location(self, num: int) -> Tuple[int, int]:
        per_block = BLOCK_SIZE // INODE_SIZE
        block = self.sb.inode_table_start + num // per_block
        offset = (num % per_block) * INODE_SIZE
        return block, offset

    def read_inode(self, num: int) -> Inode:
        block, offset = self._inode_location(num)
        data = self.disk.read_block(block)
        return Inode.unpack(data[offset:offset + INODE_SIZE])

    def write_inode(self, num: int, inode: Inode) -> None:
        block, offset = self._inode_location(num)
        data = bytearray(self.disk.read_block(block))
        data[offset:offset + INODE_SIZE] = inode.pack()
        self.disk.write_block(block, bytes(data))

    # a partir daqui, funcoes que andam na cadeia de blocos de um i-node
    # (ponteiros diretos + i-node de continuacao, se precisar)
    def _iter_blocks(self, head_inode_num: int) -> List[int]:
        blocks = []
        cur_num = head_inode_num
        seen = set()
        while cur_num != -1:
            if cur_num in seen:
                break  # protecao contra ciclo corrompido
            seen.add(cur_num)
            cur = self.read_inode(cur_num)
            for p in cur.pointers:
                if p == 0:
                    break
                blocks.append(p)
            cur_num = cur.next_inode
        return blocks

    def _grow(self, head_inode_num: int, needed_blocks: int) -> None:
        have = len(self._iter_blocks(head_inode_num))
        to_add = needed_blocks - have
        if to_add <= 0:
            return

        cur_num = head_inode_num
        cur = self.read_inode(cur_num)
        while cur.next_inode != -1:
            cur_num = cur.next_inode
            cur = self.read_inode(cur_num)

        used_in_cur = 0
        for p in cur.pointers:
            if p == 0:
                break
            used_in_cur += 1

        while to_add > 0:
            if used_in_cur < DIRECT_POINTERS:
                b = self.alloc_block()
                cur.pointers[used_in_cur] = b
                used_in_cur += 1
                to_add -= 1
            else:
                new_num = self.alloc_inode()
                new_inode = Inode(used=1, type=cur.type)
                cur.next_inode = new_num
                self.write_inode(cur_num, cur)  # persiste ponteiros + link para continuacao
                cur_num, cur = new_num, new_inode
                used_in_cur = 0
        self.write_inode(cur_num, cur)

    def _shrink(self, head_inode_num: int, needed_blocks: int) -> None:
        entries = []  # (inode_num, slot, block_num)
        cur_num = head_inode_num
        while cur_num != -1:
            cur = self.read_inode(cur_num)
            for slot, p in enumerate(cur.pointers):
                if p == 0:
                    break
                entries.append((cur_num, slot, p))
            cur_num = cur.next_inode

        if len(entries) <= needed_blocks:
            return

        to_free = entries[needed_blocks:]
        touched = {}
        for inode_num, slot, block_num in to_free:
            self.free_block(block_num)
            if inode_num not in touched:
                touched[inode_num] = self.read_inode(inode_num)
            touched[inode_num].pointers[slot] = 0
        for inode_num, inode_obj in touched.items():
            self.write_inode(inode_num, inode_obj)

        # remove i-nodes de continuacao que ficaram totalmente vazios no final da cadeia
        cur_num = head_inode_num
        cur = self.read_inode(cur_num)
        while cur.next_inode != -1:
            nxt_num = cur.next_inode
            nxt = self.read_inode(nxt_num)
            if all(p == 0 for p in nxt.pointers):
                self.free_inode(nxt_num)
                cur.next_inode = -1
                self.write_inode(cur_num, cur)
                break
            cur_num, cur = nxt_num, nxt

    # leitura/escrita do conteudo (usado tambem pro "conteudo" de symlinks,
    # que e so o caminho de destino guardado como bytes)
    def read_data(self, head_inode_num: int) -> bytes:
        inode = self.read_inode(head_inode_num)
        size = inode.size
        if size == 0:
            return b""
        blocks = self._iter_blocks(head_inode_num)
        buf = bytearray()
        remaining = size
        for b in blocks:
            if remaining <= 0:
                break
            chunk = self.disk.read_block(b)
            take = min(BLOCK_SIZE, remaining)
            buf += chunk[:take]
            remaining -= take
        return bytes(buf)

    def write_data(self, head_inode_num: int, data: bytes) -> None:
        needed_blocks = (len(data) + BLOCK_SIZE - 1) // BLOCK_SIZE
        current_blocks = len(self._iter_blocks(head_inode_num))
        if needed_blocks > current_blocks:
            self._grow(head_inode_num, needed_blocks)
        elif needed_blocks < current_blocks:
            self._shrink(head_inode_num, needed_blocks)

        blocks = self._iter_blocks(head_inode_num)
        offset = 0
        for b in blocks:
            chunk = data[offset:offset + BLOCK_SIZE]
            if len(chunk) < BLOCK_SIZE:
                chunk = chunk + b"\x00" * (BLOCK_SIZE - len(chunk))
            self.disk.write_block(b, chunk)
            offset += BLOCK_SIZE

        inode = self.read_inode(head_inode_num)
        inode.size = len(data)
        inode.modified_at = time.time()
        self.write_inode(head_inode_num, inode)

    def append_data(self, head_inode_num: int, data: bytes) -> None:
        old = self.read_data(head_inode_num)
        self.write_data(head_inode_num, old + data)

    def free_all_data(self, head_inode_num: int) -> None:
        """Libera todos os blocos de dados e i-nodes de continuacao (mas nao o i-node cabeca)."""
        self._shrink(head_inode_num, 0)

    def _init_dir_block(self, block_num: int) -> None:
        blank = DirEntry.blank().pack()
        self.disk.write_block(block_num, blank * ENTRIES_PER_BLOCK)

    def read_dir_entries(self, dir_inode_num: int) -> List[Tuple[str, int]]:
        result = []
        for b in self._iter_blocks(dir_inode_num):
            data = self.disk.read_block(b)
            for i in range(ENTRIES_PER_BLOCK):
                raw = data[i * DIRENT_SIZE:(i + 1) * DIRENT_SIZE]
                entry = DirEntry.unpack(raw)
                if entry.inode_num != EMPTY_ENTRY:
                    result.append((entry.name, entry.inode_num))
        return result

    def _find_free_dirent_slot(self, dir_inode_num: int) -> Optional[Tuple[int, int]]:
        for b in self._iter_blocks(dir_inode_num):
            data = self.disk.read_block(b)
            for i in range(ENTRIES_PER_BLOCK):
                raw = data[i * DIRENT_SIZE:(i + 1) * DIRENT_SIZE]
                entry = DirEntry.unpack(raw)
                if entry.inode_num == EMPTY_ENTRY:
                    return b, i
        return None

    def add_dir_entry(self, dir_inode_num: int, name: str, target_inode_num: int, _validate: bool = True) -> None:
        if _validate:
            self._check_name(name)
            existing = dict(self.read_dir_entries(dir_inode_num))
            if name in existing:
                raise FSError(f"{name}: já existe")

        slot = self._find_free_dirent_slot(dir_inode_num)
        if slot is None:
            current = len(self._iter_blocks(dir_inode_num))
            self._grow(dir_inode_num, current + 1)
            blocks = self._iter_blocks(dir_inode_num)
            new_block = blocks[-1]
            self._init_dir_block(new_block)
            di = self.read_inode(dir_inode_num)
            di.size = len(blocks) * BLOCK_SIZE
            di.modified_at = time.time()
            self.write_inode(dir_inode_num, di)
            slot = (new_block, 0)

        block_num, slot_idx = slot
        data = bytearray(self.disk.read_block(block_num))
        entry = DirEntry(name=name, inode_num=target_inode_num)
        data[slot_idx * DIRENT_SIZE:(slot_idx + 1) * DIRENT_SIZE] = entry.pack()
        self.disk.write_block(block_num, bytes(data))

    def remove_dir_entry(self, dir_inode_num: int, name: str) -> None:
        for b in self._iter_blocks(dir_inode_num):
            data = bytearray(self.disk.read_block(b))
            for i in range(ENTRIES_PER_BLOCK):
                raw = bytes(data[i * DIRENT_SIZE:(i + 1) * DIRENT_SIZE])
                entry = DirEntry.unpack(raw)
                if entry.inode_num != EMPTY_ENTRY and entry.name == name:
                    data[i * DIRENT_SIZE:(i + 1) * DIRENT_SIZE] = DirEntry.blank().pack()
                    self.disk.write_block(b, bytes(data))
                    return
        raise FSError(f"{name}: não encontrado")

    # so formata o campo perm do i-node pra exibicao (ls/stat) -- sem
    # checagem nenhuma, ver comentario la em cima do arquivo
    @staticmethod
    def perm_string(perm: int, itype: int) -> str:
        t = {TYPE_FILE: "-", TYPE_DIR: "d", TYPE_SYMLINK: "l"}.get(itype, "?")
        chars = ""
        for shift in (5, 4, 3, 2, 1, 0):
            bit = (perm >> shift) & 1
            chars += ("rwx"[2 - (shift % 3)]) if bit else "-"
        return t + chars

    @staticmethod
    def _check_name(name: str) -> None:
        if name in ("", ".", ".."):
            raise FSError(f"'{name}': nome inválido")
        if "/" in name:
            raise FSError(f"'{name}': nome não pode conter '/'")
        if len(name.encode("utf-8")) > MAX_NAME_LEN:
            raise FSError(f"'{name}': nome muito longo (máx. {MAX_NAME_LEN} caracteres)")

    def resolve(self, path: str, cwd_inode: Optional[int] = None,
                follow_symlink: bool = True, _depth: int = 0) -> int:
        if _depth > 20:
            raise FSError("loop de links simbólicos detectado")
        if cwd_inode is None:
            cwd_inode = self.cwd_inode
        if not path:
            raise FSError("caminho vazio")

        if path.startswith("/"):
            cur = self.sb.root_inode
        else:
            cur = cwd_inode

        parts = [p for p in path.split("/") if p != ""]
        if not parts:
            return cur

        for i, part in enumerate(parts):
            is_last = i == len(parts) - 1
            inode = self.read_inode(cur)
            if inode.type != TYPE_DIR:
                raise FSError(f"{part}: '{inode.name}' não é um diretório")
            entries = dict(self.read_dir_entries(cur))
            if part not in entries:
                raise FSError(f"{part}: arquivo ou diretório não encontrado")
            target = entries[part]
            target_inode = self.read_inode(target)
            if target_inode.type == TYPE_SYMLINK and (follow_symlink or not is_last):
                link_path = self.read_data(target).decode("utf-8", errors="replace")
                target = self.resolve(link_path, cwd_inode=cur, follow_symlink=True, _depth=_depth + 1)
            cur = target
        return cur

    def split_parent(self, path: str) -> Tuple[int, str]:
        path = path.rstrip("/")
        if path == "":
            raise FSError("caminho inválido")
        idx = path.rfind("/")
        if idx == -1:
            parent_path, name = ".", path
        elif idx == 0:
            parent_path, name = "/", path[1:]
        else:
            parent_path, name = path[:idx], path[idx + 1:]
        if name in ("", ".", ".."):
            raise FSError(f"'{path}': nome inválido")
        parent_inode = self.resolve(parent_path)
        return parent_inode, name

    def path_of(self, inode_num: int) -> str:
        if inode_num == self.sb.root_inode:
            return "/"
        components = []
        cur = inode_num
        guard = 0
        while cur != self.sb.root_inode:
            guard += 1
            if guard > 1000:
                raise FSError("caminho corrompido (profundidade excessiva)")
            entries = dict(self.read_dir_entries(cur))
            parent = entries.get("..")
            if parent is None:
                raise FSError("diretório corrompido: entrada '..' ausente")
            parent_entries = self.read_dir_entries(parent)
            name = None
            for n, num in parent_entries:
                if num == cur and n not in (".", ".."):
                    name = n
                    break
            if name is None:
                name = "?"
            components.append(name)
            cur = parent
        return "/" + "/".join(reversed(components))

    def _is_ancestor(self, maybe_ancestor: int, inode_num: int) -> bool:
        cur = inode_num
        guard = 0
        while cur != self.sb.root_inode:
            guard += 1
            if guard > 1000:
                return False
            if cur == maybe_ancestor:
                return True
            entries = dict(self.read_dir_entries(cur))
            cur = entries.get("..", self.sb.root_inode)
        return maybe_ancestor == self.sb.root_inode

    # ---- operacoes sobre arquivos ----

    def touch(self, path: str) -> int:
        parent, name = self.split_parent(path)
        existing = dict(self.read_dir_entries(parent))
        if name in existing:
            num = existing[name]
            inode = self.read_inode(num)
            inode.modified_at = time.time()
            self.write_inode(num, inode)
            return num

        num = self.alloc_inode()
        now = time.time()
        inode = Inode(
            used=1, type=TYPE_FILE, perm=DEFAULT_FILE_PERM,
            name=name, creator=self.current_user, owner=self.current_user,
            size=0, created_at=now, modified_at=now,
        )
        self.write_inode(num, inode)
        self.add_dir_entry(parent, name, num)
        return num

    def write_file(self, path: str, content: bytes, append: bool) -> int:
        parent, name = self.split_parent(path)
        existing = dict(self.read_dir_entries(parent))
        if name in existing:
            num = existing[name]
            inode = self.read_inode(num)
            if inode.type == TYPE_DIR:
                raise FSError(f"{name}: é um diretório")
        else:
            num = self.touch(path)

        if append:
            self.append_data(num, content)
        else:
            self.write_data(num, content)
        return num

    def read_file(self, path: str) -> bytes:
        num = self.resolve(path)
        inode = self.read_inode(num)
        if inode.type == TYPE_DIR:
            raise FSError(f"{path}: é um diretório")
        return self.read_data(num)

    def rm(self, path: str) -> None:
        parent, name = self.split_parent(path)
        entries = dict(self.read_dir_entries(parent))
        if name not in entries:
            raise FSError(f"{name}: arquivo não encontrado")
        num = entries[name]
        inode = self.read_inode(num)
        if inode.type == TYPE_DIR:
            raise FSError(f"{name}: é um diretório (use rmdir)")
        self.remove_dir_entry(parent, name)
        self.free_all_data(num)
        self.free_inode(num)

    def cp(self, src: str, dst: str) -> None:
        src_num = self.resolve(src)
        src_inode = self.read_inode(src_num)
        if src_inode.type != TYPE_FILE:
            raise FSError(f"{src}: cp só é suportado para arquivos")
        data = self.read_data(src_num)

        dst_final = dst
        try:
            maybe_dir = self.resolve(dst)
            if self.read_inode(maybe_dir).type == TYPE_DIR:
                base = src.rstrip("/").split("/")[-1]
                dst_final = dst.rstrip("/") + "/" + base
        except FSError:
            pass

        self.write_file(dst_final, data, append=False)

    def mv(self, src: str, dst: str) -> None:
        src_parent, src_name = self.split_parent(src)
        src_entries = dict(self.read_dir_entries(src_parent))
        if src_name not in src_entries:
            raise FSError(f"{src_name}: não encontrado")
        src_num = src_entries[src_name]
        src_inode = self.read_inode(src_num)

        dst_parent, dst_name = None, None
        try:
            maybe_dir = self.resolve(dst)
            if self.read_inode(maybe_dir).type == TYPE_DIR:
                dst_parent, dst_name = maybe_dir, src_name
        except FSError:
            pass
        if dst_parent is None:
            dst_parent, dst_name = self.split_parent(dst)

        dst_entries = dict(self.read_dir_entries(dst_parent))
        if dst_name in dst_entries:
            raise FSError(f"{dst_name}: já existe")

        if src_inode.type == TYPE_DIR:
            if src_num == dst_parent or self._is_ancestor(src_num, dst_parent):
                raise FSError("não é possível mover um diretório para dentro de si mesmo")

        self._check_name(dst_name)
        self.remove_dir_entry(src_parent, src_name)
        src_inode.name = dst_name
        src_inode.modified_at = time.time()
        self.write_inode(src_num, src_inode)
        self.add_dir_entry(dst_parent, dst_name, src_num, _validate=False)

        if src_inode.type == TYPE_DIR and dst_parent != src_parent:
            self.remove_dir_entry(src_num, "..")
            self.add_dir_entry(src_num, "..", dst_parent, _validate=False)

    def ln_s(self, target: str, link_path: str) -> int:
        parent, name = self.split_parent(link_path)
        existing = dict(self.read_dir_entries(parent))
        if name in existing:
            raise FSError(f"{name}: já existe")
        num = self.alloc_inode()
        now = time.time()
        inode = Inode(
            used=1, type=TYPE_SYMLINK, perm=DEFAULT_SYMLINK_PERM,
            name=name, creator=self.current_user, owner=self.current_user,
            size=0, created_at=now, modified_at=now,
        )
        self.write_inode(num, inode)
        self.write_data(num, target.encode("utf-8"))
        self.add_dir_entry(parent, name, num)
        return num

    # e daqui pra baixo, diretorio
    def mkdir(self, path: str) -> int:
        parent, name = self.split_parent(path)
        existing = dict(self.read_dir_entries(parent))
        if name in existing:
            raise FSError(f"{name}: já existe")

        num = self.alloc_inode()
        now = time.time()
        inode = Inode(
            used=1, type=TYPE_DIR, perm=DEFAULT_DIR_PERM,
            name=name, creator=self.current_user, owner=self.current_user,
            size=0, created_at=now, modified_at=now,
        )
        self.write_inode(num, inode)
        self.add_dir_entry(parent, name, num)
        self.add_dir_entry(num, ".", num, _validate=False)
        self.add_dir_entry(num, "..", parent, _validate=False)
        return num

    def rmdir(self, path: str) -> None:
        parent, name = self.split_parent(path)
        entries = dict(self.read_dir_entries(parent))
        if name not in entries:
            raise FSError(f"{name}: diretório não encontrado")
        num = entries[name]
        inode = self.read_inode(num)
        if inode.type != TYPE_DIR:
            raise FSError(f"{name}: não é um diretório")
        contents = [e for e in self.read_dir_entries(num) if e[0] not in (".", "..")]
        if contents:
            raise FSError(f"{name}: diretório não está vazio")

        self.remove_dir_entry(parent, name)
        self.free_all_data(num)
        self.free_inode(num)

    def ls(self, path: Optional[str] = None) -> List[Tuple[str, Inode, int]]:
        num = self.resolve(path) if path else self.cwd_inode
        inode = self.read_inode(num)
        if inode.type != TYPE_DIR:
            raise FSError(f"{path}: não é um diretório")
        result = []
        for name, child_num in sorted(self.read_dir_entries(num)):
            if name in (".", ".."):
                continue
            child = self.read_inode(child_num)
            result.append((name, child, child_num))
        return result

    def cd(self, path: str) -> None:
        num = self.resolve(path)
        inode = self.read_inode(num)
        if inode.type != TYPE_DIR:
            raise FSError(f"{path}: não é um diretório")
        self.cwd_inode = num

    def usage(self) -> dict:
        return {
            "total_blocks": self.sb.total_blocks,
            "data_blocks": DATA_BLOCKS,
            "free_blocks": self.sb.free_blocks,
            "used_data_blocks": DATA_BLOCKS - self.sb.free_blocks,
            "block_size": self.sb.block_size,
            "total_inodes": self.sb.num_inodes,
            "free_inodes": self.sb.free_inodes,
            "used_inodes": self.sb.num_inodes - self.sb.free_inodes,
            "disk_size_bytes": TOTAL_BLOCKS * BLOCK_SIZE,
            "metadata_blocks": RESERVED_BLOCKS,
        }
