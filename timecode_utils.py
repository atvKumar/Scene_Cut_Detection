def convert_ms2frames(fps, ms):
    """Converts Milliseconds to frames
    :param: Video Frame Rate e.g '25'
    :return: Integer (framerate)"""
    return int(round(float(fps) / 1000 * float(ms)))


def convert_timecode(fps, timecode):
    """Converts HH:MM:SS.mm to HH:MM:SS:FF"""
    timecode = timecode.strip()
    hh, mm, ss_ms = timecode.split(':')
    ss, ms = ss_ms.split('.')
    ff = convert_ms2frames(fps, ms)
    if len(str(ff)) < 2:
        ff = str(ff).zfill(2)
    return str(hh) + ':' + str(mm) + ':' + str(ss) + ':' + str(ff)


def timecode_to_seconds(timecode, fps=0):
    hh, mm, ss, ff, ms = [0, 0, 0, 0, 0.0]
    if timecode.count(':') == 3:
        hh, mm, ss, ff = [int(i) for i in timecode.split(':')]
    elif timecode.count(':') == 2:
        if '.' in timecode:
            hh, mm, ss_ms = [i for i in timecode.split(':')]
            hh = int(hh)
            mm = int(mm)
            ss, ms = [int(ss_ms.split('.')[0]), float('0.'+ss_ms.split('.')[1])]
        else:
            hh, mm, ss = [int(i) for i in timecode.split(':')]
    if not ms:
        if fps == 0:
            return (hh*60*60) + (mm*60) + (ss*1)
        else:
            if ff < fps:
                ff *= 10
            return (hh*60*60) + (mm*60) + (ss*1) + round((1/fps * ff), 2)
    else:
        return (hh*60*60) + (mm*60) + (ss*1) + ms


def seconds_to_frames(total_seconds, fps):
    return int(total_seconds * fps)