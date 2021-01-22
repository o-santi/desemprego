#import pyautogui
from PIL import Image
import numpy as np
from time import sleep, perf_counter
#from tqdm import tqdm
from pynput.keyboard import Listener, Key

import pywintypes
import win32gui, win32ui, win32con, win32api

import cv2 as cv
from os.path import getsize
import ctypes 


class VeryBadRecorder():

    def __init__(self):
        self.image_array = []
        self.time_array = []
        self.key_pressed =  False
        ctypes.windll.user32.SetProcessDPIAware()


    def transform_coordinates(self, x, y):
        #monitor_handle = win32api.MonitorFromPoint(win32gui.GetCursorPos())
        #info = win32api.GetMonitorInfo(monitor_handle)
        if x > 1920:
            x = (x * 1920) // 2400
            y = (y * 1080) // 1350
        return x, y

    
    def wait_for_keypress(self, modo, key=Key.caps_lock):
        ''' modo definir o modo como trigger on press ou trigger on release'''
        assert modo in ['on_release', 'on_press']

        def on_release(released_key):
            if released_key == key and modo == 'on_release': #TODO : change to any key
                listener.stop() # stop listener
        def on_press(pressed_key):
            if pressed_key == key and modo == 'on_press': # TODO: change to any key
                listener.stop() # stop listener
        with Listener(on_release=on_release, on_press=on_press) as listener:
            listener.join() # start listener

            
    def _select_record_area(self):
        self.wait_for_keypress('on_release') # espera o tab ser apertado
        self.hwnd = win32gui.GetDesktopWindow() # windows bullshit
        self.handler_dc = win32gui.GetWindowDC(self.hwnd) # more bs
        x1, y1 = self.transform_coordinates(*win32gui.GetCursorPos())
        def on_release(key):
            if key == Key.caps_lock: # define function to be called on on_release callback
                self.key_pressed = True # set flag
                return False  # stop listener
        listener = Listener(on_release=on_release)
        listener.start() # start listener
        while True:
            if self.key_pressed:
                self.key_pressed = False # reset flag
                break # stop the drawing
            mouse_pos = self.transform_coordinates(*win32gui.GetCursorPos())
            win32gui.DrawFocusRect(self.handler_dc, (x1, y1, *mouse_pos))
            win32gui.DrawFocusRect(self.handler_dc, (x1, y1, *mouse_pos))
            # draw the same rectangle twice because its XOR, self-erases when applied twice
        x2, y2 = self.transform_coordinates(*win32gui.GetCursorPos()) # after second key press, get second mouse position
        self.left = x1 if x1 < x2 else x2
        self.top = y1 if y1 < y2 else y2
        self.width = abs(x1 - x2)
        self.height = abs(y1 - y2)
        #print('Selecionado: Segundo monitor') if left >= 1920 else print('Selecionado: Primeiro monitor')
        self.wait_for_keypress('on_release') # wait for third key press
        #print(self.left, self.top, self.width, self.height)
        print("Gravando...")
        self._start_recording()

    def _start_recording(self):     
        # create a bitmap object 
        self.img_dc = win32ui.CreateDCFromHandle(self.handler_dc)
        t2 = perf_counter()
        
        def on_press(key):
            if key == Key.caps_lock:
                self.key_pressed = True
                return False

        listener = Listener(on_press=on_press)
        listener.start()
        while True: # THIS IS VERY TRASHY, not only fps is unstable but fps cannot be properly capped, and time-syncing is still kinda in the bruh stage.
            # i would love to actually use windows media encoder api with python, but i fear that this would need to be done with actuall C++ code + their sdk.
            if self.key_pressed: # checks if flag is set
                self.key_pressed = False # reset flag
                break  # stop recording 
            t1 = t2
            #ALL THE WINDOWS BS
            mem_dc = self.img_dc.CreateCompatibleDC()
            screenshot = win32ui.CreateBitmap()
            screenshot.CreateCompatibleBitmap(self.img_dc, self.width, self.height)
            mem_dc.SelectObject(screenshot)
            #up to here is windows bs
            mem_dc.BitBlt((0, 0), (self.width, self.height), self.img_dc, (self.left, self.top),win32con.SRCCOPY) # <--- this screenshots and saves to screenshot variable 
            bmpstr = screenshot.GetBitmapBits(True) # read it
            im = Image.frombuffer(
                'RGB',
                (self.width, self.height),
                bmpstr, 'raw', 'BGRX', 0, 1) # transform to bytes-string and save as Image Object
            mem_dc.DeleteDC() # don't forget to delete your device contexts
            win32gui.DeleteObject(screenshot.GetHandle())  # and your handles
            t2 = perf_counter() # trying to controll time-syncing, but not very good tbh
            time_delta = (t2 - t1) * 1000 # time in miliseconds between the last frame and this one
            #print(delta)
            #sleep(1/fps_cap - time_delta) <-- had this idea but sleep is not precise enough to keep fps rate in control, so fps is kinda wild while not implemented
            self.image_array.append(im) 
            self.time_array.append(time_delta)
        win32gui.ReleaseDC(self.hwnd, self.handler_dc) # do not forget to release your DCs or windows will get MAD 

        
    def _save_to_file(self, filename, file_extension):
        filepath = f'output/{filename}'
        if file_extension == 'gif':
            #image_array, durations = otimizar(image_array, time_array)
            video_fps = 1000 * len(self.image_array) / np.array(self.time_array).sum() # fps average rough estimate, when the standard deviation is small
            self.image_array[0].save(f'{filepath}.gif',
                                format='gif',
                                append_images=self.image_array[1:],
                                save_all=True,
                                duration=self.time_array,
                                loop=0,
                                optimize=True) # save through PIL's builtin
            file_size = getsize(rf'{filepath}.gif') # in byts
            print(f"{filename}.gif was saved. [fps: {video_fps:.2f}, {file_size / (1024 * 1024):.2f} mbs]")

        elif file_extension == 'mp4':
            #fourcc = cv.videowriter_fourcc(*"h264") <-- i do think ffmpeg is needed for this to work
            fourcc = 0x21 # little bit of a hack, throws an error but still encodes with h264 (or at least i think it does), don't @ me
            video_fps = 1000 * len(self.image_array) / np.array(self.time_array).sum()
            vid_writer = cv.VideoWriter(f'{filepath}.mp4', fourcc, video_fps, (self.width, self.height))
            [vid_writer.write(cv.cvtColor(np.array(frame), cv.COLOR_BGR2RGB)) for frame in self.image_array] # this time through 
            vid_writer.release()
            file_size = getsize(f'{filepath}.mp4') # em bytes
            print(f"{filename}.mp4 was saved. [fps: {video_fps:.2f}, {file_size / (1024 * 1024):.2f} mbs]")


    def _optimize_gif(self):
        '''compares each pair of frames to see if they are equal:
           if they are, add their durations, if they arent, just append to the array'''
        new_image_array, durations = [], []
        duration = self.time_array[0]
        last = self.image_array[0]
        last_compare = np.array(last.convert("L").resize((32,32), resample=Image.BICUBIC)).astype(np.int)
        for index, frame in enumerate(self.image_array[1:]):
            frame_compare = np.array(frame.convert("L").resize((32,32), resample=Image.BICUBIC)).astype(np.int)
            if np.abs(frame_compare - last_compare).sum() > 10:
                new_image_array.append(last)
                durations.append(duration)
                last = frame
                last_compare = frame_compare
                duration = self.time_array[index]
            else:
                duration += self.time_array[index]
        new_image_array.append(last) # append last frame
        durations.append(duration)
        self.image_array = new_image_array
        self.time_array = durations

        
    def record(self):
        self._select_record_area()
        filename = input('Digite o nome do arquivo: ')
        if filename:
            file_extension = input('Digite o tipo de arquivo (gif ou mp4):')
            assert file_extension in ['gif', 'mp4']
            if file_extension == 'gif':
                self._optimize_gif()
            self._save_to_file(filename, file_extension)
            

'''
def editar_video(image_array, time_array, filename):
    index = 0
    actual_frames = [True for _ in range(len(image_array))]
    while True:
        frame = image_array[index]
        cv_image = cv.cvtColor(np.array(frame.convert('RGB')), cv.COLOR_RGB2BGR)
        cv.putText(cv_image,
                    f"FRAME:{index+1} / {len(image_array)} {'@' if actual_frames[index] else '#'}",
                   (0, cv_image.shape[0]),
                   cv.FONT_HERSHEY_SIMPLEX, 1, (0,0,255))
        cv.imshow(f'{filename}', cv_image)
        key_pressed = cv.waitKey(0)
        if key_pressed == ord('a'):
            index -=1
        elif key_pressed == ord('d'):
            index +=1
        elif key_pressed == ord('A'):
            actual_frames[index] = False
            index -=1
        elif key_pressed == ord('D'):
            actual_frames[index] = False
            index +=1
        elif key_pressed == 9: #tab
            print("Edição terminada.")
            break
        index %= len(image_array)
    cv.destroyAllWindows()
    new_image_array = [image_array[i] for i in range(len(actual_frames)) if actual_frames[i]]
    new_time_array = [time_array[i] for i in range(len(actual_frames)) if actual_frames[i]]
    return new_image_array
'''

if __name__ == '__main__':
    r = VeryBadRecorder()
    r.record()

