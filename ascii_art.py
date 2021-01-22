from PIL import Image, ImageOps
import matplotlib.pyplot as plt
from numpy import array
from math import ceil
import ctypes
import sys

kernel32 = ctypes.windll.kernel32
kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)

file_name = sys.argv[1]

img = Image.open(file_name).convert('L')
largura, altura = img.size
buffer_height = 50
buffer_width = 50
resize_factor = max(ceil(altura*100/buffer_width), ceil(largura*100/buffer_height))
img = img.resize((int(largura * 100/resize_factor), int(altura *100/resize_factor)), 0)
pixel_array = list(img.getdata())
pixel_array = array(pixel_array).reshape((img.size[1], img.size[0]))
ascii_art = ''
ascii_table = ["#", "@","/","=", ".", " ", " "]
#ascii_table = ["PEI", "DO"]
ascii_table.reverse()
for coluna in pixel_array:
    for pixel in coluna:
        #print(coluna, pixel)
        #red, green, blue, alfa = pixel
        ascii_char_val = int(len(ascii_table) * pixel/256)
        #char_index += 1
        #char_index %= len(ascii_table)
        #ascii_art += f"\033[38;2;{red %255};{green%255};{blue%255}m{ascii_table[char_index]}"
        ascii_art += 2 * f"{ascii_table[ascii_char_val]}"
    #ascii_art += '\033[!p\n'
    ascii_art += '\n'
print(ascii_art)
print((largura, altura), img.size, resize_factor / 100)
with open(file_name[:-4] + ".txt", "w", encoding="utf-8") as file:
    file.write(ascii_art)
#plt.imshow(pixel_array)
#plt.show()
