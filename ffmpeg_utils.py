from timecode_utils import convert_timecode, timecode_to_seconds
from timecode_utils import seconds_to_frames
from platform import system
from time import sleep
# from PIL import Image
# from os.path import basename, join as pathjoin
# from os import getcwd, sep, makedirs
import subprocess as sp
# import numpy as np


SYSTEM = system()
IS_OSX = SYSTEM == 'Darwin'
IS_WINDOWS = SYSTEM == 'Windows'

_ffmpeg_bin = 'ffmpeg' if IS_OSX else 'ffmpeg.exe'  # ffmpeg binary location
_ffprobe_bin = 'ffprobe' if IS_OSX else 'ffprobe.exe' # ffprobe binary location
_ffmpeg_detected = False  # Checked once upon module import
_ffprobe_detected = False  # Checked once upon module import
_ffmpeg_exists = False
_ffprobe_exists = False


class FFMPEG_Missing(Exception):
    pass


class FFPROBE_Missing(Exception):
    pass


class PixelFormat:
    """pixel format and bit per pixels for each pixel"""
    def __init__(self, line):
        self.input = line[0] == 'I'
        self.output = line[1] == 'O'
        self.hardware = line[2] == 'H'
        self.paletted = line[3] == 'P'
        self.bitstream = line[5] == 'B'
        options = [t for t in line[8:].split(' ') if t != '']
        self.name, self.components, self.bpp = (options[0],
                                                int(options[1]),
                                                int(options[2]))

    def __repr__(self):
        io = 'I' if self.input else '.'
        io += 'O' if self.output else '.'
        return '<PixelFormat {0} {1} {2} {3}>'.format(self.name,
                                                      io,
                                                      self.components,
                                                      self.bpp)


class Format:
    """file formats supported by ffmpeg"""
    types = {'D': 'Demuxing supported', 'E': 'Muxing supported',
             'DE': 'Demuxing & Muxing supported'}

    def __init__(self, line):
        self.demuxing = line[1] == 'D'
        self.muxing = line[2] == 'E'
        self.type = self.types[line[1:3].split()[0]]
        self.short_name = line[4:].split()[0]
        self.full_name = ' '.join(line[4:].split()[1:])

    def __repr__(self):
        muxing = ''
        if self.demuxing:
            muxing += 'D'
        if self.muxing:
            muxing += 'E'
        return '<Format {0} {1}>'.format(self.short_name, self.type)


class Codec:
    """video/audio/subtitle codecs supported by ffmpeg"""
    types = {'V': 'video', 'A': 'audio', 'S': 'subtitle', 'D': 'data'}

    def __init__(self, line):
        self.decoding = line[1] == 'D'
        self.encoding = line[2] == 'E'
        self.subtitle = line[3] == 'S'
        self.intra = line[4] == 'I'
        self.lossy = line[5] == 'L'
        self.lossless = line[6] == 'S'
        self.type = self.types[line[3]]
        self.short_name = line[8:].split()[0]
        self.full_name = ' '.join(line[8:].split()[1:])

    def __repr__(self):
        return '<Codec {0} for {1}>'.format(self.short_name, self.type)


def _check_ffmpeg(bin=_ffmpeg_bin):
    global _ffmpeg_detected
    if _ffmpeg_detected:
        return  # So that check is done only once
    try:
        p = sp.Popen(bin, stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE,)
        del p
        return True
    except EnvironmentError:
        return False


def _check_ffprobe(bin=_ffprobe_bin):
    global _ffprobe_detected
    if _ffprobe_detected:
        return  # So that check is done only once
    try:
        p = sp.Popen(bin, stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE,)
        del p
        return True
    except EnvironmentError:
        return False


def _plugins_gen(option, sep=' -------', stdpipe='stderr'):
    p = get_ffmpeg(option)
    first_skip = True
    if stdpipe == 'stdin':
        stdpipe = p.stdin
    if stdpipe == 'stdout':
        stdpipe = p.stdout
    if stdpipe == 'stderr':
        stdpipe = p.stderr
    for line in stdpipe.readlines():
        line = line.rstrip()
        if first_skip:
            if line[:len(sep)] == sep:
                first_skip = False
            continue
        if line == '':
            break
        yield line
    del p


def get_pipe(cmd, option=None, print_cmd=False):
    if option:
        if type(option) == str:
            cmd.append(option)
        if type(option) == list:
            cmd += option
    if print_cmd:
        print ' '.join(cmd)
    return sp.Popen(cmd, stdin=sp.PIPE, stdout=sp.PIPE, stderr=sp.PIPE,)


def get_ffmpeg(option=None, print_cmd=False):
    """get pipes from ffmpeg process with stderr"""
    _check_ffmpeg()
    cmd = [_ffmpeg_bin]
    return get_pipe(cmd, option, print_cmd)


def get_ffprobe(option=None):
    """get pipes from ffprobe process with stderr"""
    _check_ffprobe()
    cmd = [_ffprobe_bin]
    return get_pipe(cmd, option)


def get_ffmpeg_bin():
    _check_ffmpeg()
    return _ffmpeg_bin


def get_ffprobe_bin():
    _check_ffprobe()
    return _ffprobe_bin


def set_ffmpeg_bin(path):
    global _ffmpeg_bin
    _ffmpeg_bin = path


def set_ffprobe_bin(path):
    global _ffprobe_bin
    _ffprobe_bin = path


def get_ffmpeg_info(full_info=False):
    """get infomation about ffmpeg(included versions)"""
    p = get_ffmpeg(' -version')
    if not full_info:
        version = p.stderr.readlines()[0][15:20]
        del p
        return version
    result = {}
    for line in p.stderr.readlines():
        if line[:6] == 'FFmpeg' or line[:6] == 'ffmpeg':
            result['ffmpeg'] = line[15:line.find(',')]
            continue
        if line[2:2+5] == 'built':
            result['built'] = line[11:].rstrip()
            continue
        if line[2:15] == 'configuration':
            result['configuration'] = line[17:].rstrip()
            continue
        if line[2:5] == 'lib':
            line = line[2:].rstrip()
            idx = line.find(' ')
            name = line[:idx]
            result[name] = line[idx:].lstrip()
            continue
    del p
    return result


def get_ffprobe_info(full_info=False):
    """get infomation about ffprobe(included versions)"""
    p = get_ffprobe(' -version')
    if not full_info:
        version = p.stderr.readlines()[0][16:21]
        del p
        return version
    result = {}
    for line in p.stderr.readlines():
        if line[:7] == 'FFprobe' or line[:7] == 'ffprobe':
            result['ffprobe'] = line[16:line.find(',')]
            continue
        if line[2:2+5] == 'built':
            result['built'] = line[11:].rstrip()
            continue
        if line[2:15] == 'configuration':
            result['configuration'] = line[17:].rstrip()
            continue
        if line[2:5] == 'lib':
            line = line[2:].rstrip()
            idx = line.find(' ')
            name = line[:idx]
            result[name] = line[idx:].lstrip()
            continue
    del p
    return result


def get_codecs():
    """get codecs for ffmpeg"""
    result = {}
    for line in _plugins_gen('-codecs', stdpipe='stdout'):
        result[line[8:].split()[0]] = Codec(line)
    return result


def get_formats():
    """get formats for ffmpeg"""
    result = {}
    for line in _plugins_gen('-formats', sep=' --', stdpipe='stdout'):
        result[line[4:]] = Format(line)
    return result


def get_pixel_formats():
    """get pix_fmts for ffmpeg"""
    result = {}
    for line in _plugins_gen('-pix_fmts', sep='-----', stdpipe='stdout'):
        pix = PixelFormat(line)
        result[pix.name] = pix
    return result


def ffprobe_vdata(video):
    ffprobe_bin = get_ffprobe_bin()
    cmd = [ffprobe_bin,
           '-select_streams', 'v',
           '-show_streams',
           video]
    pipe = sp.Popen(cmd, stdout=sp.PIPE, close_fds=True)
    results = pipe.stdout.read()
    # print len(results), type(results), results
    data = {i.split('=')[0]: i.split('=')[1] for i in results.split('\n')[1:-2]}
    return data


def ffprobe_video(video):
    """
    Get Video's Video Information using FFPROBE
    :param video: Path to Video
    :return: dict
    """
    ffprobe_bin = get_ffprobe_bin()
    cmd = [ffprobe_bin, video]
    pipe = sp.Popen(cmd, stderr=sp.PIPE, close_fds=True)
    results = pipe.stderr.read()
    timecode, duration, frame_size, fps = ['00:00:00:00', '00:00:00', '0x0', 0]

    for line in results.split('\n'):
        if 'timecode' in line:
            timecode = line.split()[2]
        elif 'Duration' in line:
            duration = line.split()[1][:-1]
        elif 'Stream' in line and 'Video' in line:
            reversed_line = line.split(',')[::-1]
            frame_size = [x.split()[0] for x in reversed_line if 'x' in x][0]
            fps = float([x.split()[0] for x in reversed_line if 'fps' in x][0])

    # duration = convert_timecode(fps, duration)
    total_seconds = timecode_to_seconds(duration, fps)
    width, height = [int(i) for i in frame_size.split('x')]
    total_frames = seconds_to_frames(total_seconds, fps)
    is_even = total_frames % 2 == 0
    is_odd = is_even == False
    pipe.terminate()

    return {'start_timecode': timecode,
            'duration': convert_timecode(fps, duration),
            'seconds': total_seconds,
            'width': width,
            'height': height,
            'frames': total_frames,
            'is_even': is_even,
            'is_odd': is_odd,
            'fps': fps}


def video_to_images(input_video, output_file, fmt='_%05d.jpg', degradation=5,
                    wait=True):
    x = get_ffmpeg(['-i', input_video, '-deinterlace', '-an', '-vf',
                    'scale=iw/%s:-1' % degradation,
                    '-f', 'image2', output_file + fmt])
    if wait:
        while x.returncode != 0:
            sleep(1)
            x.communicate()
        return x.returncode == 0
    else:
        sleep(0.1)


#Depreciated function
# def ffmpeg_stream(video, delay1='-00:00:02', delay2='00:00:00',
#                   even_frames=False):
#     video_data = ffprobe_video(video)
#     fps = str(int(video_data['fps']))
#     cmd = [get_ffmpeg_bin(),
#            '-ss', delay1,  # delay 1
#            '-i', video,
#            '-r', fps,
#            '-deinterlace',
#            '-an', '-s', '480x270',
#            # '-vf', "w3fdif",  # -filter video deinterlace
#            '-ss', delay2,  # delay 2
#            '-f', 'image2pipe',  # to pipe
#            '-pix_fmt', 'rgb24',  # pixel format
#            '-vcodec', 'rawvideo', '-']
#     # print ' '.join(cmd)
#     loop_count = video_data['frames']  # Inital value
#     if even_frames:
#         if video_data['is_odd']:
#             loop_count = video_data['frames']-1  # Make Even
#     loop_count += (int(video_data['fps'])*2+3)  # Add offset
#     pipe = sp.Popen(cmd, stdout=sp.PIPE, bufsize=10**8)
#     for i in xrange(0, loop_count):
#         # read width*height*3 bytes (== 1 frame)
#         raw_image = pipe.stdout.read(video_data['width']*video_data['height']*3)
#         # transform the byte read into a numpy array
#         image = np.fromstring(raw_image, dtype=np.uint8)
#         # reshape the array to fit in numpy
#         image = image.reshape((video_data['height'], video_data['width'], 3))
#         if i > int(video_data['fps']*2):
#             yield image
#     pipe.terminate()


#Depreciated function
# def ffmpeg_stream_filter(video, delay1='-00:00:02', delay2='00:00:00',
#                          even_frames=False):
#     video_stream = ffmpeg_stream(video, delay1, delay2, even_frames)
#     yield video_stream.next()
#     yield video_stream.next()
#     video_stream.next()  # Skip frame 2
#     yield video_stream.next()
#     video_stream.next()  # Skip frame 4
#     for frame in video_stream:
#         yield frame

#Depreciated function
# def video_to_image(video, output_directory=getcwd()):
#     filename = basename(video).split('.')[0]
#     video_stream = ffmpeg_stream(video)
#     path = pathjoin(output_directory, filename + sep)
#     makedirs(path)
#     path += filename
#     Image.fromarray(video_stream.next()).save(
#         pathjoin(output_directory, path+'0.jpg'))
#     Image.fromarray(video_stream.next()).save(
#         pathjoin(output_directory, path+'1.jpg'))
#     video_stream.next()  # Skip frame 2
#     Image.fromarray(video_stream.next()).save(
#         pathjoin(output_directory, path+'2.jpg'))
#     video_stream.next()  # Skip frame 4
#     i = 3
#     for frame in video_stream:
#         # print i
#         Image.fromarray(frame).save(
#             pathjoin(output_directory, path + '{0}.jpg'.format(i)))
#         i += 1


if __name__ == '__main__':
    if _check_ffmpeg():
        _ffmpeg_detected = True
    else:
        raise FFMPEG_Missing('Please make sure ffmpeg on PATH, '
                             'or set_ffmpeg_bin')
    if _check_ffprobe():
        _ffprobe_detected = True
        _ffprobe_exists = True
    else:
        raise FFPROBE_Missing('Please make sure ffprobe on PATH, '
                             'or set_ffprobe_bin')