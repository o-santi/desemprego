from PIL import Image
import numpy as np
from tqdm import tqdm
import time

import pywintypes
import win32gui, win32ui, win32api, win32console

import asyncio
import aiofiles
import argparse
import mmap


class AsyncGifPlayer():

    def __init__(self,filename, mode, char, console):
        self.gif = Image.open(filename) #open on RGBA
        self.frame_count = self.gif.n_frames
        self.filename = filename
        self.console = console # if True opens a new console to show the gif 
        self.width = self.gif.width
        self.height = self.gif.height
        self.char_array = [" ", ".", "-", "*", "/", "=", "#","░", "▒", "▓"]
        self.screen_array = [] # dimensions are width by height so width * height elements      
        self.char = char
        self.duration = self.gif.info.get("duration", 43) / 1000
        self.mode = mode # either ascii-characters or colored
        
        
    def create_terminal_window(self):
        """
        creates the console screen buffer that can be printed to
        this only works on windows now, but should be easier to implement on unix cuz windows KEKW
        also, only worked for fixed console widths and heights, I still wasnt able to change it to
        arbitrary size, so all the gifs will be stretched to this ratio for now
        
        TODO: change the fucking window size
        """
        if self.console:
            win32console.FreeConsole() # detaches the process from the one that was used
            win32console.AllocConsole() # and creates a new one
        self.window = win32console.GetConsoleWindow() # gets the new window, just for grabs, not actually being used
        self.console_handle = win32console.CreateConsoleScreenBuffer()        
        console_info = self.console_handle.GetConsoleScreenBufferInfo()
        """
        @o_santi -> was trying to resize the console with these things but no luck 
                    windows hates me
        
        largest_x, largest_y = console_info["MaximumWindowSize"].X, console_info["MaximumWindowSize"].Y
        min_x, min_y = win32api.GetSystemMetrics(28), win32api.GetSystemMetrics(29)
        if self.width/self.height >=1:
            new_x, new_y = int(largest_x * self.height/self.width), largest_y
        else:
            new_x, new_Y = largest_x, int(largest_y * self.width / self.height)
        
        self.console_handle.SetConsoleWindowInfo(False, win32console.PySMALL_RECTType(0, 0, new_x, new_y))
        self.console_handle.SetConsoleScreenBufferSize(win32console.PyCOORDType(new_x, new_y))
        time.sleep(10)
        """
        
        console_mode = self.console_handle.GetConsoleMode()    
        self.console_handle.SetConsoleMode(int(console_mode | 0x004)) # sets the Enable Virtual Terminal Console Mode
        self.frame_size = (console_info["Size"].X, console_info["Size"].Y)

        
    def create_gif_buffer(self):
        """
        creates the array that hold the actual pixel values (the colors of the chars)
        
        TODO: implement async version, where each frame is run by a single await create_frame and then
        used to create the buffer, it'll run A LOT faster
        """
        
        assert self.mode in ["color", "ascii"] # make sure that the mode is correct
        
        for frame_index in tqdm(range(self.frame_count)): # iterate through the frames in the gif
            
            self.gif.seek(frame_index) 
            
            if self.mode == "color":
                frame = self.gif.convert("RGB").resize((self.frame_size[0], self.frame_size[1])) # convert to rgb and resize
                pixel_array = np.array(frame.getdata()).reshape((self.frame_size[0], self.frame_size[1], 3)) # create the numpy array and reshape 
                self.screen_array.append("") # start the string that will hold the actual ansi-codes
                last_pixel = 0, 0, 0 # hold the last pixel value so that it can be compared (for optimization purposes)
                
            elif self.mode == "ascii":
                frame = self.gif.convert("L").resize((self.frame_size[0], self.frame_size[1]))
                pixel_array = np.array(frame.getdata()).reshape((self.frame_size[1], self.frame_size[0], 1))
                self.screen_array.append("")
                
            descriptor = len(f"{self.filename} -- 000 -- fps: 000") # descriptor of the gif

            for line_index, line in enumerate(pixel_array):
                if line_index == 0:
                    # write descriptor at first line
                    self.screen_array[frame_index] += f"\033[7m{self.filename} -- {frame_index:03d} -- fps: 000\033[0m"
                    line = line[descriptor:]

                for pixel in line:
                    if self.mode == "color":
                        
                        r, g, b = pixel
                        r_index = int(6 * r / 256)
                        g_index = int(6 * g / 256)
                        b_index = int(6 * b / 256)
                        number_code = 16 + (r_index * 36 + g_index * 6 + b_index)
                        
                        """
                        uses ansi 6 bit color codes (so 216 coloring)
                        could try to use 256 bit ansi coloring, but the player runs smoother this way
                        >>> and it is more aesthetic (in my opinion) <<<
                        """
                        
                        if np.any(last_pixel != number_code):
                            pixel_string = f"\033[48;5;{number_code}m" # color the background with the coloring
                            self.screen_array[frame_index] += pixel_string
                            last_pixel = number_code
                        self.screen_array[frame_index] += self.char
                            
                    elif self.mode == "ascii":
                        char = self.char_array[ int(len(self.char_array) * pixel/256) ]
                        self.screen_array[frame_index] += char
            self.screen_array[frame_index] += "\033[H"

            
    def create_frame_bytes(self):
        """
        uses mmaps to read/write faster
        @o_santi ->actually i wanted to create a virtual memory mapping of the stdout, so that the maximum read/write speed could be reached
        but i think this would put me in the gray area of the programmers because it seems like a crime
        either way, I will find a way to do this >:(
        """
        self.frames_bytes = []
        for index, string in enumerate(self.screen_array):
            #bytes_array.write(bytes(self.screen_array[index], encoding='utf-8'))
            mmap_buffer = mmap.mmap(-1, length=len(bytes(string, encoding='utf-8')), access=mmap.ACCESS_WRITE)  # create the map
            mmap_buffer[:] = bytes(string, encoding='utf-8') # write the frame to it
            mmap_buffer.flush() # flush it so that it is written to memory
            self.frames_bytes.append(mmap_buffer)
            

    async def draw_gif(self):
        try:
            self.create_terminal_window() 
            self.create_gif_buffer()
            self.create_frame_bytes()
            self.console_handle.SetConsoleActiveScreenBuffer()
            async with aiofiles.open("CONOUT$", "wb") as file_object:
                index = 0
                descriptor = len(f"{self.filename} -- 000 -- fps: 000") + 1
                # for some reason, the actual file-position is one char further than the actual len
                # maybe because of all the ansi-code that is being written, honestly idk
                while True:
                    t1 = time.perf_counter_ns()
                    frame_mmap = self.frames_bytes[index] # get current frame
                    frame_mmap.seek(0) # seek to the start of the frame
                    await file_object.write(frame_mmap.read()) # print
                    index += 1 
                    index %= self.frame_count # loop it
                    if (delta := (time.perf_counter_ns() - t1)/10**9) < self.duration  :
                        await asyncio.sleep(self.duration - delta) # make sure that it only sleeps when it actually is printing faster than it should
                        # >>>perf_counter_ns is post python 3.7<<<
                    fps = f'{int(10**9/((time.perf_counter_ns() - t1))):03d}'
                    self.frames_bytes[index][descriptor:descriptor + 3] = bytes(fps, encoding='utf-8') # write fps to position
                    
        except KeyboardInterrupt: # stop by crtl-c'ing
            # i know this is not good practice,
            # will change later
            # TODO: fix this shit
            self.console_handle.Close()
            [mmap_obj.close() for mmap_obj in self.frames_bytes]
            print("Terminado com sucesso")


    def play(self):
        """
        runs the main loop to draw the gif and show it in the console
        """
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.draw_gif())
        loop.close



        
def main():
    parser = argparse.ArgumentParser(description = "plays cool gifs on the terminal",
                                     epilog= "created by @o_santi, follow me on twitter @o_santi_")
    parser.add_argument('-c','-C' ,'--console' ,help='whether or not a new console is created to show the gif',
                        action='store_true')
    parser.add_argument('filename', help='filename to be shown')
    parser.add_argument('mode', help='color for colors or ascii for black and white text')
    parser.add_argument('--char', help="char to print when in colored mode",
                        default=' ')

    args = parser.parse_args()
    if args.filename:
        player = AsyncGifPlayer(args.filename, args.mode, args.char, args.console)
        player.play()
        
            
if __name__ == "__main__":
    main()