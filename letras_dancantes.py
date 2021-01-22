from PIL import Image
import numpy as np
from io import BytesIO
#from helper_classes import show_function_info
import textwrap
import re

class EscrevedorDeMerda:

    def __init__(self, string, char_width=30, char_height=25):
        self.string = string
        self.char = (char_width, char_height)
        self.max_width = 500
        
    def write(self):
        self.generate_gif_array()
        self.concatenate_images()
        self.save()

    @show_function_info()
    def concatenate_images(self):
        filename = input('de o filename do background: ')
        frame_numbers = len(self.gif_array[0])
        width = max([len(string) for string in self.string_array]) * self.char[0]
        height = len(self.string_array) * self.char[1]
        if filename != "nenhum":
            self.final_gif = [Image.open(filename) for _ in range(frame_numbers)]
        else:
            self.final_gif = [Image.new("RGBA", (width, height)) for _ in range(frame_numbers)]
        frame_width = 0
        frame_height = 0
        for frame_array in self.gif_array:
            if frame_array == 'espaco':
                frame_width += self.char[0]
                continue
            if frame_array == "jumpline":
                frame_width = 0
                frame_height += self.char[1]
                continue
            for index, frame in enumerate(frame_array):
                self.final_gif[index].alpha_composite(frame.convert(mode="RGBA"), (frame_width, frame_height))
            frame_width += self.char[0]


    def resize_gif(self, gif):
        frame_array = []
        for frame in range(gif.n_frames):
            gif.seek(frame)
            frame_array.append(gif.resize(self.char, resample=Image.BILINEAR)) # change only width to 10 to normalize
        return frame_array

    
    def generate_gif_array(self):
        self.gif_array = []
        self.lines = 0
        self.string_array = textwrap.wrap(self.string, width=self.max_width//self.char[0])
        print(self.string_array)
        for string in self.string_array:
            for letra in string:
                if letra == " ":
                    self.gif_array.append("espaco")
                else:
                    self.gif_array.append(self.resize_gif(Image.open(f"imagem/letras/{letra}.gif")))
            self.gif_array.append("jumpline")

        
    def save(self):
        self.final_gif[0].save(f"imagem/{self.string}.gif",
                          save_all=True,
                          loop=0,
                          append_images=self.final_gif[1:])


if __name__ == "__main__":
    escrivao = EscrevedorDeMerda(input("digite o texto pra ser penis-musicado: "))
    escrivao.write()

