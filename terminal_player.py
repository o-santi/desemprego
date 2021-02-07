"""
Really bad video player made to play on the terminal.
Can also print images.

"""


from PIL import Image, UnidentifiedImageError
import numpy as np
from tqdm import tqdm
import time

from pynput import keyboard

import asyncio
import aiofiles
import argparse
import mmap
import threading
import concurrent.futures

import cv2
import filetype
import sys


class TerminalPlayer:
    def __init__(self, filename, mode, char, console, fps_cap):
        self.filename = filename
        self.filetype = filetype.guess(self.filename)
        self.console = console  # if True, opens a new console to show the gif
        self.fps_cap = fps_cap # if False, disables fps caps and plays as fast as it can
        self.char_array = [" ", ".", "-", "*", "/", "=", "#"]
        self.char = char
        self.supported_filetypes = ["gif", "mp4"]
        self.modes = ["ascii", "color", "color216"]
        assert mode in self.modes
        self.mode = mode  # either ascii-characters or colored
        self.image_frames_array = []
        self.screen_array = (
            []
        )  # dimensions are width by height so width * height elements

    def open_pillow_image(self, gif_object):
        """
        maybe here the mmaps should already be used to read and write faster
        TODO: idk, test this stupid idea later, maybe it is faster
        """
        self.is_animated = getattr(gif_object, "is_animated", False)
        self.width = gif_object.width
        self.height = gif_object.height
        self.frame_count = int(getattr(gif_object, "n_frames", 1))
        self.duration = gif_object.info.get("duration", 41.6) / 1000  # default to 24fps
        self.sound = False

        for frame in range(self.frame_count):
            gif_object.seek(frame)
            if self.mode == "ascii":
                frame = gif_object.convert("L").resize(self.frame_size).getdata()
                frame = np.reshape(frame, (*self.frame_size, 1))
            elif self.mode.startswith("color"):
                frame = gif_object.convert("RGB").resize(self.frame_size).getdata()
                frame = np.reshape(frame, (*self.frame_size, 3))
            self.image_frames_array.append(frame)

    def open_opencv_image(self, cap):
        """
        Opens the video using opencv-python
        """
        fps = cap.get(cv2.CAP_PROP_FPS)
        self.duration = 1 / fps
        self.width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        self.height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        self.frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.is_animated = True
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
            frame = cv2.resize(frame, self.frame_size)
            if self.mode == "ascii":
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                frame = np.reshape(frame, (*self.frame_size, 1))
            elif self.mode.startswith("color"):
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frame = np.reshape(frame, (*self.frame_size, 3))
            self.image_frames_array.append(frame)
        cap.release()

    def handle_file_types(self):
        """
        handles multiple filetype
        sets the following aspect for the self object:

        image_frames_array -> holds the arrays of the pixel values
                              each frame is a numpy array
        frame_count -> number of frames in video
        filetype -> filetype
        width
        height
        duration -> time to sleep between frames
        TODO: play sound lol
        """
        try:
            self.open_pillow_image(Image.open(self.filename)) # tries to open with pillow
        except UnidentifiedImageError:
            cap = cv2.VideoCapture(self.filename) # if didnt open, try it with cv2
            if cap.isOpened():
                self.open_opencv_image(cap)
            else:
                print("Sua imagem/video não pôde ser aberta.")
                raise TypeError # TODO: create error type, this is just a place-holder

    def create_terminal_window(self):
        """
        creates the console screen buffer that can be printed to
        this only works on windows now, but should be easier to implement on unix cuz windows KEKW
        also, only worked for fixed console widths and heights, I still wasnt able to change it to
        arbitrary size, so all the gifs will be stretched to this ratio for now

        TODO: change the fucking window size
        """
        if sys.platform == "win32":
            import pywintypes
            import win32gui, win32ui, win32api, win32console

            if self.console:
                win32console.FreeConsole()  # detaches the process from the one that was used
                win32console.AllocConsole()  # and creates a new one
            self.window = (
                win32console.GetConsoleWindow()
            )  # gets the new window, just for grabs, not actually being used
            self.console_handle = win32console.CreateConsoleScreenBuffer()
            console_mode = self.console_handle.GetConsoleMode()
            console_info = self.console_handle.GetConsoleScreenBufferInfo()
            self.console_handle.SetConsoleMode(
                int(console_mode | 0x004)
            )  # sets the Enable Virtual Terminal Console Mode
            self.frame_size = (console_info["Size"].X, console_info["Size"].Y)

            """
        elif sys.platform.startswith('linux'):
            import curses
            
            screen_curses_object = curses.initscr()
            self.frame_size =  self.screen_curses_object.getmaxyx()[:-1]
            screen_curses_object.endwin()
            """

    def map_video_buffer_to_threads(self):
        """
        maps the video frames to the processing threads, to generate the frames
        """
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            self.screen_array = list(
                tqdm(
                    executor.map(
                        self.create_gif_buffer,
                        range(self.frame_count),
                        self.image_frames_array,
                    ),
                    total=self.frame_count,
                )
            )

    def create_gif_buffer(self, frame_index, pixel_array):
        """
        creates the array that hold the actual pixel values (the colors of the chars)
        this function only need the pixel_data, so that it is not dependent to any format
        as long as it is properly formatted (correct width and height) it will work
        """
        screen_array = ""
        if self.mode == "color":
            last_pixel = 0, 0, 0
        elif self.mode == "color216":
            last_pixel = 0

        descriptor = len(f"{self.filename} -- 000 -- fps: 000")  # descriptor of the gif
        for line_index, line in enumerate(pixel_array):
            if line_index == 0 and self.is_animated:
                # write descriptor at first line
                screen_array += (
                    f"\033[7m{self.filename} -- {frame_index:03d} -- fps: 000\033[0m"
                )
                line = line[descriptor:]

            for pixel in line:
                if self.mode == "color":

                    r, g, b = pixel
                    if np.any(last_pixel != pixel):
                        pixel_string = f"\033[48;2;{r};{g};{b}m"  # color the background with the coloring
                        screen_array += pixel_string
                        last_pixel = pixel
                    screen_array += self.char

                elif self.mode == "color216":
                    r, g, b = pixel
                    r_index = int(6 * r / 256)
                    g_index = int(6 * g / 256)
                    b_index = int(6 * b / 256)
                    number_code = 16 + (r_index * 36 + g_index * 6 + b_index)
                    if last_pixel != number_code:
                        pixel_string = f"\033[48;5;{number_code}m"
                        screen_array += pixel_string
                        last_pixel = number_code
                    screen_array += self.char

                elif self.mode == "ascii":
                    pixel = pixel[0]
                    char = self.char_array[int(len(self.char_array) * pixel / 256)]
                    screen_array += char
            #screen_array += "\n"
        screen_array += "\033[H"
        return screen_array

    def create_frame_bytes(self):
        """
        uses mmaps to read/write faster
        @o_santi -> actually i wanted to create a virtual memory mapping of the stdout, so that the maximum read/write speed could be reached
        but i think this would put me in the gray area of the programmers because it seems like a really shitty idea 
        either way, I will find a way to do this >:(
        """
        self.frames_bytes = []
        for index, string in enumerate(self.screen_array):
            # bytes_array.write(bytes(self.screen_array[index], encoding='utf-8'))
            mmap_buffer = mmap.mmap(
                -1,
                length=len(bytes(string, encoding="utf-8")),
                access=mmap.ACCESS_WRITE,
            )  # create the map
            mmap_buffer[:] = bytes(string, encoding="utf-8")  # write the frame to it
            mmap_buffer.flush()  # flush it so that it is written to memory
            self.frames_bytes.append(mmap_buffer)

    async def blit_screen(self, frame_index):
        """
        prints the index-th frame of the screen_array to the screen
        """
        t1 = time.perf_counter_ns()
        frame_mmap = self.frames_bytes[frame_index]  # get current frame
        frame_mmap.seek(0)  # seek to the start of the frame
        await self.file_object.write(frame_mmap.read())  # print
        if (delta := (time.perf_counter_ns() - t1) / 10 ** 9) < self.duration and self.fps_cap:
            await asyncio.sleep(
                self.duration - delta
            )
            delta += self.duration - delta
            # make sure that it only sleeps when it actually is printing faster than it should
            # >>>perf_counter_ns is post python 3.7<<<
        if self.is_animated:
            fps = f"{int(1/delta):03d}"
            self.frames_bytes[(frame_index + 1) % self.frame_count][
                self.descriptor_len : self.descriptor_len + 3
            ] = bytes(
                fps, encoding="utf-8"
            )  # write fps to position on the next frame

    async def play_animated(self):
        
        def on_key_press_stop(key):
            if key == keyboard.Key.esc:
                self.is_playing = False
                listener.stop()

        async with aiofiles.open("CONOUT$", "wb") as self.file_object:
            self.descriptor_len = len(f"{self.filename} -- 000 -- fps: 000") + 1
            # for some reason, the actual file-position is one char further than the actual len
            # maybe because of all the ansi-code that is being written, honestly idk
            if self.is_animated:
                listener = keyboard.Listener(on_press=on_key_press_stop)
                listener.start()

                frame_index = 0
                self.is_playing = True
                while self.is_playing:
                    await self.blit_screen(frame_index)
                    frame_index += 1
                    frame_index %= self.frame_count
            else:
                await self.blit_screen(0)  # print the first frame so that still images can also be shown
                with keyboard.Listener(on_press=on_key_press_stop) as listener:
                    listener.join() # waits for the key to be pressed so that you can see the image

    async def draw_to_screen_main(self):
        self.create_terminal_window()
        self.handle_file_types()
        self.map_video_buffer_to_threads()
        self.create_frame_bytes()
        self.console_handle.SetConsoleActiveScreenBuffer()
        await self.play_animated()

        
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
            asyncio.run(self.draw_to_screen_main())
        except KeyboardInterrupt:
            print(
                "Interrupted by user. The intended way of closing is with the ESC key"
            )
        finally:
            self.close()


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="written by @o_santi, follow me on twitter @o_santi_",
    )
    parser.add_argument(
        "-c",
        "-C",
        "--console",
        help="whether or not a new console is created to show the gif",
        action="store_true",
    )
    parser.add_argument("filename", help="filename to the video or image to be shown")
    parser.add_argument(
        "mode",
        help="'color' for 24-bit colors (best to display images); \
              'color216' for 6-bit coloring (best to play videos);  \
              'ascii' for black and white text (best for aesthetics)",
    )
    parser.add_argument(
        "--char", help="char to print when in colored mode", default=" "
    )
    parser.add_argument(
        "--fps-cap",
        "-f",
        help="whether or not the video's normal fps should be respected. defaults to false",
        action="store_false",
    )

    args = parser.parse_args()
    if args.filename:
        terminal_player = TerminalPlayer(args.filename, args.mode, args.char, args.console, args.fps_cap)
        terminal_player.play()


if __name__ == "__main__":
    main()
