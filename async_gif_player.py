from PIL import Image
import numpy as np
from tqdm import tqdm
import time

import pywintypes
import win32gui, win32ui, win32api, win32console
from pynput import keyboard

import asyncio
import aiofiles
import argparse
import mmap
import threading
import concurrent.futures

import cv2
import filetype


class AsyncGifPlayer():

    def __init__(self,filename, mode, char, console):
        self.filename = filename
        self.filetype = filetype.guess(self.filename)
        self.console = console # if True opens a new console to show the gif 
        self.char_array = [" ", ".", "-", "*", "/", "=", "#", "░", "▒", "▓"]
        self.char = char
        self.supported_filetypes = ['gif', 'mp4']
        self.modes = ['ascii', 'color']
        assert mode in self.modes
        self.mode = mode # either ascii-characters or colored
        self.image_frames_array = []
        self.screen_array = [] # dimensions are width by height so width * height elements      
        
        
    def handle_file_types(self):
        '''
        tries to handle multiple filetypes
        sets the following aspect for the self object:
        
        image_frames_array -> holds the arrays of the pixel values
                              each frame is a numpy array
        frame_count -> number of frames in video
        filetype -> filetype
        width 
        height
        duration -> time to sleep between frames
        TODO: play sound lol
        '''
        if self.filetype.extension not in self.supported_filetypes:
            raise TypeError
        if self.filetype.extension == 'gif':
            gif_object = Image.open(self.filename)
            self.width = gif_object.width
            self.height = gif_object.height
            self.frame_count = gif_object.n_frames
            self.duration = gif_object.info.get("duration", 41.6) / 1000 # default to 24fps
            self.sound = False
            
            for frame in range(gif_object.n_frames):
                gif_object.seek(frame)
                if self.mode == 'ascii':
                    frame = gif_object.convert("L").resize(self.frame_size).getdata()
                    frame = np.reshape(frame, (*self.frame_size, 1))
                elif self.mode == 'color':
                    frame = gif_object.convert("RGB").resize(self.frame_size).getdata()
                    frame = np.reshape(frame, (*self.frame_size, 3))
                self.image_frames_array.append(frame)

        elif self.filetype.extension == 'mp4':
            """
            this probably can read a lot of extensions because of opencv
            but i can't know for sure because it is fourcc-dependent,
            the best way would be to try to open the format and see if it actually worked

            TODO: change this shit to more than just mp4
            """
            cap = cv2.VideoCapture(self.filename)
            fps = cap.get(cv2.CAP_PROP_FPS)
            self.duration = 1/fps
            self.width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            self.height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            self.frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            while(cap.isOpened()):
                ret, frame = cap.read()
                if not ret:
                    break
                frame = cv2.resize(frame, self.frame_size)
                if self.mode == 'ascii':
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    frame = np.reshape(frame, (*self.frame_size, 1))
                elif self.mode == 'color':
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    frame = np.reshape(frame, (*self.frame_size, 3))
                self.image_frames_array.append(frame)
            cap.release()

            
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
        """
        @o_santi -> was trying to resize the console with these things but no luck 
                    windows hates me
        
                self.console_handle.SetConsoleWindowInfo(False, win32console.PySMALL_RECTType(0, 0, new_x, new_y))
        self.console_handle.SetConsoleScreenBufferSize(win32console.PyCOORDType(new_x, new_y))
        time.sleep(10)
        console_info = self.console_handle.GetConsoleScreenBufferInfo()
        largest_x, largest_y = console_info["MaximumWindowSize"].X, console_info["MaximumWindowSize"].Y
        min_x, min_y = win32api.GetSystemMetrics(28), win32api.GetSystemMetrics(29)
        
        if self.width/self.height >=1:
            new_x, new_y = int(min_y * self.width/self.height), min_y
        else:
            new_x, new_y = largest_x, int(largest_x * self.width/self.height)
        self.console_handle.SetConsoleWindowInfo(True, win32console.PySMALL_RECTType(0, 0, 1, 1))
        self.console_handle.SetConsoleScreenBufferSize(win32console.PyCOORDType(new_x, new_y))        
        self.console_handle.SetConsoleWindowInfo(False, win32console.PySMALL_RECTType(0, 0, new_x, new_y))
        #win32gui.MoveWindow(self.window, 0, 0, self.width, self.height, False)
        """
        console_mode = self.console_handle.GetConsoleMode()
        console_info = self.console_handle.GetConsoleScreenBufferInfo()
        self.console_handle.SetConsoleMode(int(console_mode | 0x004)) # sets the Enable Virtual Terminal Console Mode
        self.frame_size = (console_info["Size"].X, console_info["Size"].Y)

    
    def map_video_buffer_to_threads(self):
        """
        maps the video frames to the processing threads, to generate the frames 
        """
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            self.screen_array = list(tqdm(executor.map(self.create_gif_buffer,
                                             range(self.frame_count),
                                             self.image_frames_array), total=self.frame_count))
       
    def create_gif_buffer(self, frame_index, pixel_array):
        """
        creates the array that hold the actual pixel values (the colors of the chars)
        this function only need the pixel_data, so that it is not dependent to any format
        as long as it is properly formatted (correct width and height) it will work
        """
        screen_array = ""
        if self.mode == "color":
            last_pixel = 0,0,0
        
        descriptor = len(f"{self.filename} -- 000 -- fps: 000") # descriptor of the gif
        
        for line_index, line in enumerate(pixel_array):
            if line_index == 0:
                # write descriptor at first line
                screen_array += f"\033[7m{self.filename} -- {frame_index:03d} -- fps: 000\033[0m"
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
                        screen_array += pixel_string
                        last_pixel = number_code
                    screen_array += self.char
                    
                elif self.mode == "ascii":
                    pixel = pixel[0]
                    char = self.char_array[int(len(self.char_array) * pixel/256)]
                    screen_array += char
        screen_array += "\033[H"
        return screen_array

    
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
    
        def on_key_press_stop(key):
            if key == keyboard.Key.esc:
                self.is_playing = False
                listener.stop()
                
        self.create_terminal_window()
        self.handle_file_types()
        self.map_video_buffer_to_threads()
        self.create_frame_bytes()
        self.console_handle.SetConsoleActiveScreenBuffer()    
        async with aiofiles.open("CONOUT$", "wb") as file_object:
            index = 0
            descriptor = len(f"{self.filename} -- 000 -- fps: 000") + 1
            # for some reason, the actual file-position is one char further than the actual len
            # maybe because of all the ansi-code that is being written, honestly idk
            listener = keyboard.Listener(on_press=on_key_press_stop)
            listener.start()
            self.is_playing = True
            while self.is_playing:
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

    def close(self):
        """
        stops everything that needs stopin'
        and closes everything that needs closin'
        """
        [mmap_obj.close() for mmap_obj in self.frames_bytes]
        self.console_handle.Close()
        print("Terminado com sucesso")
        
    
    def play(self):
        """
        runs the main loop to draw the gif and show it in the console
        pretty simple
        no biggies
        """
        try:
            asyncio.run(self.draw_gif())
        except KeyboardInterrupt:
            print('Interrupted by user. The intended way of closing is with the ESC key')
        finally:
            self.close()
    
        
def main():
    parser = argparse.ArgumentParser(description = "plays cool videos on the terminal",
                                     epilog= "written by @o_santi, follow me on twitter @o_santi_")
    parser.add_argument('-c','-C' ,'--console' , help='whether or not a new console is created to show the gif',
                        action='store_true')
    parser.add_argument('filename', help='filename to the video to be shown')
    parser.add_argument('mode', help='\'color\' for colors or \'ascii\' for black and white text')
    parser.add_argument('--char', help="char to print when in colored mode",
                        default=' ')

    args = parser.parse_args()
    if args.filename:
        player = AsyncGifPlayer(args.filename, args.mode, args.char, args.console)
        player.play()
        
            
if __name__ == "__main__":
    main()
