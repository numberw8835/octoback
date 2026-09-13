from modules.engine import Engine
from modules.utils.utils import get_file_hash, get_file_hash_optimized

result1 = get_file_hash("/home/warden/Tmp/example problem/Text File.txt")
print(result1)
result2 = get_file_hash_optimized("/home/warden/Tmp/example problem/Text File.txt")
print(result2)

print(result1 == result2)