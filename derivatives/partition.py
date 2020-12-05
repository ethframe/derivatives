import sys
from typing import Callable, List, Tuple, TypeVar

CHARSET_END = sys.maxunicode + 1

T = TypeVar('T')
U = TypeVar('U')
Partition = List[Tuple[int, T]]


def make_merge_fn(update_item: Callable[[T, U], T]
                  ) -> Callable[[Partition[T], Partition[U]], Partition[T]]:

    def merge(acc: Partition[T], val: Partition[U]) -> Partition[T]:
        result: Partition[T] = []
        acc_it = iter(acc)
        val_it = iter(val)
        acc_end, acc_item = next(acc_it)
        val_end, val_item = next(val_it)
        while True:
            if acc_end == val_end:
                result.append((acc_end, update_item(acc_item, val_item)))
                if acc_end == CHARSET_END:
                    return result
                else:
                    acc_end, acc_item = next(acc_it)
                    val_end, val_item = next(val_it)
            elif acc_end < val_end:
                result.append((acc_end, update_item(acc_item, val_item)))
                acc_end, acc_item = next(acc_it)
            else:
                result.append((val_end, update_item(acc_item, val_item)))
                val_end, val_item = next(val_it)

    return merge
