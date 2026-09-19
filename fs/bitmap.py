"""
Bitmap generico usado tanto para controlar i-nodes livres/ocupados quanto
blocos de dados livres/ocupados (item exigido no enunciado: "controle sobre
quais blocos/i-nodes estao livres ou ocupados").
"""

from __future__ import annotations


class Bitmap:
    def __init__(self, data: bytearray, size_bits: int):
        self.data = data
        self.size_bits = size_bits

    def get(self, i: int) -> bool:
        return bool(self.data[i // 8] & (1 << (i % 8)))

    def set(self, i: int, value: bool) -> None:
        if value:
            self.data[i // 8] |= 1 << (i % 8)
        else:
            self.data[i // 8] &= ~(1 << (i % 8)) & 0xFF

    def find_free(self, start: int = 0):
        for i in range(start, self.size_bits):
            if not self.get(i):
                return i
        return None

    def count_free(self, start: int = 0) -> int:
        return sum(1 for i in range(start, self.size_bits) if not self.get(i))
