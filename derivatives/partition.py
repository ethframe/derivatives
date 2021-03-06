from typing import Callable, Iterable, Iterator, List, Tuple, TypeVar

CHARSET_END = 0x100

T = TypeVar('T')
U = TypeVar('U')
Partition = List[Tuple[int, T]]
IterablePartition = Iterable[Tuple[int, T]]
PartitionIterator = Iterator[Tuple[int, T]]


def make_merge_fn(update: Callable[[T, U], T], update_copy: Callable[[T, U], T]
                  ) -> Callable[[IterablePartition[T],
                                 IterablePartition[U]], Partition[T]]:

    def merge(acc: IterablePartition[T], val: IterablePartition[U]
              ) -> Partition[T]:
        result: Partition[T] = []
        acc_it = iter(acc)
        val_it = iter(val)
        acc_end, acc_item = next(acc_it)
        val_end, val_item = next(val_it)
        try:
            while True:
                if acc_end == val_end:
                    result.append((acc_end, update(acc_item, val_item)))
                    acc_end, acc_item = next(acc_it)
                    val_end, val_item = next(val_it)
                elif acc_end < val_end:
                    result.append((acc_end, update(acc_item, val_item)))
                    acc_end, acc_item = next(acc_it)
                else:
                    result.append((val_end, update_copy(acc_item, val_item)))
                    val_end, val_item = next(val_it)
        except StopIteration:
            return result

    return merge


def make_merge_copy_fn(update_copy: Callable[[T, U], T]
                       ) -> Callable[[IterablePartition[T],
                                      IterablePartition[U]], Partition[T]]:

    return make_merge_fn(update_copy, update_copy)
