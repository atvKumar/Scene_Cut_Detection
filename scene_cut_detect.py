from matplotlib import colors
from skimage.filter import canny
from skimage import measure
from skimage.morphology import dilation, square
from os import getcwd
from os.path import basename, join as pathjoin, splitext, isfile
from PIL import Image
from tempfile import mkdtemp
from shutil import rmtree
from ffmpeg_utils import ffprobe_video, video_to_images
from pytimecode import PyTimeCode
import numpy as np


def invert(image):
    """
    Invert color values in ndarray
    :param image: ndarray
    :return: new copy of ndarray
    """
    if image.dtype == 'bool':
        tmp = image.copy()
        for hno, y in enumerate(tmp):
            for rno, x in enumerate(y):
                tmp[hno, rno] = not x
        return tmp
    elif image.dtype == 'float32':
        return 1 - image
    elif image.dtype == 'uint8':
        return 255 - image


def add(image1, image2):
    tmp = image1.astype('float32') + image2.astype('float32')
    for hno, y in enumerate(tmp):
        for rno, x in enumerate(y):
            if x > 255:
                tmp[hno, rno] = 255
    return tmp.astype('uint8')


def desaturate(image):
    """
    Desaturate, or Greyscale a color image
    :param image: 3D ndarray
    :return: 2D array
    """
    greyscale = colors.rgb_to_hsv(image)
    greyscale[:, :, 1] = 0  # Desaturate the image
    greyscale = colors.hsv_to_rgb(greyscale)
    greyscale = greyscale[:, :, 0]  # 3D array to 2D
    return greyscale


def arrayInfo(image):
    """ Print out ndarray info """
    print("Image size in bytes : {}".format(image.size))
    print("Image size Height(y) * Width(x) * Channels(RGBA)"
          " : {}".format(image.shape))
    print("Image Data Type : {}".format(image.dtype))
    print("NDArray Diemensions : {}".format(image.ndim))
    print(image)


def edge_change_ratio(frame1, frame2, sigma=3, low_threshold=20,
                      high_threshold=80, distance=24, edge_width=10,
                      float_accuracy=3):
    """
    Calculate Edge Change Ratio for the given 2 frames (n-1, n)
    :param frame1: Frame N-1
    :param frame2: Frame N
    :param sigma: Edge detection level
    :param low_threshold: Dark threshold
    :param high_threshold: Bright threshold
    :param distance: Dialtion Distance
    :param edge_width: Distance of Edges Measured
    :param float_accuracy: Floating point precision
    :return: Float
    """
    frame1_grey = desaturate(frame1)
    frame2_grey = desaturate(frame2)

    frame1_edge = canny(frame1_grey, sigma, low_threshold, high_threshold)
    frame2_edge = canny(frame2_grey, sigma, low_threshold, high_threshold)

    frame1_inv_edge = invert(frame1_edge).astype('uint8') * 255
    frame2_inv_edge = invert(frame2_edge).astype('uint8') * 255

    frame1_contours = measure.find_contours(frame1_inv_edge, edge_width)
    frame2_contours = measure.find_contours(frame2_inv_edge, edge_width)

    frame1_dialate = dilation(frame1_edge, square(distance))
    frame2_dialate = dilation(frame2_edge, square(distance))

    frame1_comp = frame1_inv_edge + frame2_dialate
    frame2_comp = frame2_inv_edge + frame1_dialate

    frame1_comp_contours = measure.find_contours(frame1_comp, edge_width)
    frame2_comp_contours = measure.find_contours(frame2_comp, edge_width)

    try:
        return round(
            max(float(len(frame1_comp_contours)) / float(len(frame1_contours)),
                float(len(frame2_comp_contours)) / float(len(frame2_contours))),
            float_accuracy) * 100
    except ZeroDivisionError:
        return 0


def ImgSeqStream(path, filename, fmt='_%05d.jpg'):
    digits = len(fmt % 1)
    max_number = int('9' * digits)
    for i in xrange(1, max_number):
        imgfile = pathjoin(path, filename + fmt % i)
        if not isfile(imgfile):
            break
            # raise IOError(imgfile + ' Not found!')
        else:
            with open(imgfile) as fp:
                img = Image.open(fp)
                pix = np.array(img.getdata(), dtype=np.uint8).reshape(
                    (img.size[1], img.size[0], 3))
                yield pix


def SCD_Using_ECR(video, tmp_path=getcwd(), fmt='_%05d.jpg',
                  global_threshold=80, degradation=5):
    """
    Scene Cut Detection using Edge Change Ratio of a given Video
    :param video: Path to Video
    :return: None
    """
    tmp_folder = mkdtemp(dir=tmp_path)  # Create a temp dir
    tmp_filename = splitext(basename(video))[0]  # Get name from video
    output_path = pathjoin(tmp_folder, tmp_filename)  # Join
    video_to_images(video, output_path, fmt, degradation,
                    wait=False)  # Convert Video to Images

    video_info = ffprobe_video(video)
    print video_info
    # Default 00:00:00:00 Source In Timecode
    begin_timecode = PyTimeCode(video_info['fps'], '00:00:00:00')
    # Source's Running Timecode
    video_timecode = PyTimeCode(video_info['fps'], '00:00:00:00')
    # Source's Start Timecode else Defaults to 00:00:00:00
    start_timecode = PyTimeCode(video_info['fps'], video_info['start_timecode'])
    # Source's Duration in Timecode
    end_timecode = PyTimeCode(video_info['fps'],
                              '00:00:00:00') + video_info['frames']
    edit_list = list()

    with open(pathjoin(getcwd(), '%s.txt' % tmp_filename), 'w+') as fp:
        vstream = ImgSeqStream(tmp_folder, tmp_filename, fmt)
        for i, current_frame in enumerate(vstream):
            if i > 0:
                ecr = edge_change_ratio(previous_frame, current_frame,
                                        float_accuracy=2)
                print video_timecode, i, ecr
                if ecr > global_threshold:
                    fp.writelines('{2},{0},{1},CUT!\n'.format(i, ecr,
                                                              video_timecode))
                    edit_list.append(video_timecode)
                else:
                    fp.writelines('{2},{0},{1}\n'.format(i, ecr,
                                                         video_timecode))
            previous_frame = current_frame
            video_timecode += 1

    rmtree(tmp_folder, True)
    print edit_list
    createEDL(begin_timecode, start_timecode, end_timecode, edit_list,
              tmp_filename, '%s.edl' % tmp_filename)


def createEDL(begin_timecode, start_timecode, end_timecode, edit_list,
              video_filename, edl_filename):
    _fmt = '{0:03n}        AX AA/V C        {1} {2} {3} {4}\n'
    _cmt = '* FROM CLIP NAME:  {0}\n\n'.format(video_filename)
    with open(edl_filename, 'w+') as fp:
        fp.write('TITLE:  {0}\n'.format(video_filename))
        fp.write('FCM: NON-DROP FRAME\n\n')

        fp.write(_fmt.format(1, begin_timecode, edit_list[0]-1, start_timecode,
                             start_timecode+edit_list[0]-1))
        fp.write(_cmt)
        # print _fmt.format(1, begin_timecode, edit_list[0], start_timecode,
        #                   start_timecode+edit_list[0])
        # print _cmt

        for i, cut in enumerate(edit_list, 2):
            # cut = PyTimeCode(video_info['fps'], cut)
            if i-1 < len(edit_list):
                y = edit_list[i-1] - 1
                fp.write(_fmt.format(i, cut, y, start_timecode+cut,
                                     start_timecode+y))
                fp.write(_cmt)
                # print _fmt.format(i, cut, y, start_timecode+cut,
                #                   start_timecode+y)
                # print _cmt
            elif i > len(edit_list):
                fp.write(_fmt.format(i, cut, end_timecode, start_timecode+cut,
                                     start_timecode+end_timecode))
                fp.write(_cmt)
                # print _fmt.format(i, cut, end_timecode, start_timecode+cut,
                #                   start_timecode+end_timecode)
                # print _cmt