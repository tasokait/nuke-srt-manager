import nuke
import hiero.core
import hiero.ui
import hiero.exporters
from PySide6.QtWidgets import QInputDialog
from PySide6.QtWidgets import QMessageBox
import re
import random
import os

cvbin = None
def parse_srt(file_path):
    subtitles = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            blocks = content.strip().split('\n\n')
            
            for block in blocks:
                lines = block.strip().split('\n')
                if len(lines) >= 2:
                    timing = lines[1].split(' --> ')
                    if len(timing) == 2:
                        start_time = convert_time_to_frames(timing[0])
                        end_time = convert_time_to_frames(timing[1])
                        text = '\n'.join(lines[2:]).lstrip(' ')
                        subtitles.append({
                            'start': start_time,
                            'end': end_time,
                            'text': text
                        })
    except Exception as e:
        print(f"Error parsing SRT file: {e}")
    return subtitles

def convert_time_to_frames(time_str):
    active_seq = hiero.ui.activeSequence()
    frame_rate = active_seq.framerate().toInt()
    match = re.match(r'(\d{2}):(\d{2}):(\d{2}),(\d{3})', time_str)
    if match:
        hours, minutes, seconds, milliseconds = map(int, match.groups())
        total_seconds = hours * 3600 + minutes * 60 + seconds
        frames = total_seconds * frame_rate + int(milliseconds * frame_rate / 1000)
        return frames
    return 0

def create_text_layers(subtitles,ifcut,subind):
    nuke.Undo.begin("making the subtitles")
    sequence = hiero.ui.activeSequence()
    if not sequence:
        print("No active sequence found!")
        return
    
    subtitle_track = None
    for track in sequence.videoTracks():
        if track.name() == "Subtitles":
            subtitle_track = track
            break
    if not subtitle_track:
        subtitle_track = hiero.core.VideoTrack("Subtitles")
        sequence.addTrack(subtitle_track)
    
    for sub in subtitles:
        duration = sub['end'] - sub['start']
        if duration <= 0:
            continue
        if ifcut == QMessageBox.Yes:
                sequence.razorAt(sub['start'])
                sequence.razorAt(sub['end']+1)
        text_clip = hiero.core.EffectTrackItem("Text2", sub['start'], sub['end'])
        clip_name = re.sub(r'[^a-zA-Z\s]', '',sub['text']).split(" ")[0]
        if clip_name.isdigit():
            if len(sub['text'].split(" ")) > 2 :
                clip_name = clip_name.join(sub['text'].split(" ")[1])
            else:
                clip_name = "just_number" + clip_name
        if clip_name == "":
            clip_name = "subtitle"
        print(clip_name)
        text_clip.setName(clip_name)
        
        text_node = text_clip.node()
        text_node["font_size"].setValue(50)
        text_node["global_font_scale"].setValue(0.75)
        text_node["box"].setValue([360, 50, 1560, 250])
        text_node["xjustify"].setValue(1)
        text_node["yjustify"].setValue(2)
        text_node["color"].setValue([1,0.5,0,1])
        text_node['message'].setValue(sub['text'])
        
        subtitle_track.addSubTrackItem(text_clip,subind)
        nuke.Undo.end()
    if ifcut == QMessageBox.Yes:
        nuke.Undo.begin("deleting unused parts")
        sub_trackitems = subtitle_track.subTrackItems()[0]
        for v_track in sequence.videoTracks():
            if v_track.name() == "Subtitles":
                continue
            for a_track in sequence.audioTracks():
                for v_item in v_track.items():
                    for a_item in a_track.items():
                        if (v_item.timelineIn() == a_item.timelineIn() and v_item.timelineOut() == a_item.timelineOut() and not v_item.isLinked(a_item)) and v_item.source() == a_item.source() and v_item.source().mediaSource() == a_item.source().mediaSource():
                            v_item.link(a_item)
                            break
        for track in sequence.videoTracks() + sequence.audioTracks():
            if track.name() == "Subtitles":
                continue
            for item in track.items():
                matched = False
                for subs in sub_trackitems:
                    if subs.timelineIn() == item.timelineIn() and item.timelineOut() == subs.timelineOut():
                        matched = True
                        break
                if not matched:
                    track.removeItem(item)
        for track in sequence.videoTracks() + sequence.audioTracks():
            if track.name() == "Subtitles":
                origIn = track.subTrackItems()[0][0].timelineIn()
                track.subTrackItems()[0][0].setTimelineIn(0)
                track.subTrackItems()[0][0].setTimelineOut(track.subTrackItems()[0][0].timelineOut() - origIn)
            else:
                origIn = track.items()[0].timelineIn()
                track.items()[0].setTimelineIn(0)
                track.items()[0].setTimelineOut(track.items()[0].timelineOut() - origIn)
        for i in range(len(sub_trackitems)-1):
            gap = sub_trackitems[i+1].timelineIn() - sub_trackitems[i].timelineOut()
            sub_trackitems[i+1].setTimelineIn(sub_trackitems[i+1].timelineIn() - gap + 1)
            sub_trackitems[i+1].setTimelineOut(sub_trackitems[i+1].timelineOut() - gap + 1)
            for track in sequence.videoTracks():
                if track.name() == "Subtitles":
                    continue
                if i >= len(track.items()):
                    break
                track.items()[i+1].setTimelineIn(track.items()[i+1].timelineIn() - gap + 1)
                track.items()[i+1].setTimelineOut(track.items()[i+1].timelineOut() - gap + 1)
        nuke.Undo.end()

    print(f"Added {len(subtitles)} subtitle clips to the timeline.")

def import_srt_subtitles():
    file_path= nuke.getFilename("Select SRT File", "*.srt")
    
    if not file_path:
        print("No file selected.")
        return
    msgBox = QMessageBox()
    msgBox.setText("Do you want other tracks get cutted based on subtitles?")
    msgBox.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
    msgBox.setDefaultButton(QMessageBox.No)
    ifcut = msgBox.exec()
    subtitles = parse_srt(file_path)
    if subtitles:
        create_text_layers(subtitles,ifcut,0)
    else:
        print("No subtitles found or invalid SRT file.")
def import_srt_subtitles_read():
    file_path= nuke.getFilename("Select SRT File", "*.srt")
    
    if not file_path:
        print("No file selected.")
        return
    subtitles = parse_srt(file_path)
    if subtitles:
        create_text_layers(subtitles,QMessageBox.No,1)
    else:
        print("No subtitles found or invalid SRT file.")
def add_stroke():
    sequence = hiero.ui.activeSequence()
    if not sequence:
        print("No active sequence found!")
        return
    
    subtitle_track = None
    for track in sequence.videoTracks():
        if track.name() == "Subtitles":
            subtitle_track = track
            break
    nuke.Undo.begin("adding the strokes")
    maxxed = len(subtitle_track.subTrackItems())
    for subs in subtitle_track.subTrackItems()[maxxed-1]:
        og_node = subs.node()

        text_clip = hiero.core.EffectTrackItem("Text2", subs.timelineIn(), subs.timelineOut())
        text_clip.setName("Subtitle_stroke")
        
        text_node = text_clip.node()
        text_node["font_size"].setValue(50)
        text_node["global_font_scale"].setValue(0.75) 
        text_node["box"].setValue(og_node["box"].value())
        text_node["xjustify"].setValue(1)
        text_node["yjustify"].setValue(2)
        text_node["color"].setValue([1,0.5,0,1])
        text_node["enable_shadows"].setValue(True)
        text_node["shadow_distance"].setValue(0)
        text_node["shadow_size"].setValue(5)
        text_node["shadow_opacity"].setValue(1)
        text_node["shadow_color"].setValue([1,1,1,1])
        text_node['message'].setValue(og_node['message'].value())
        
        subtitle_track.addSubTrackItem(text_clip,maxxed)

        og_node["enable_shadows"].setValue(True)
        og_node["shadow_opacity"].setValue(0.9)
        og_node["shadow_distance"].setValue(6.5)
        og_node["shadow_size"].setValue(6.5)
    nuke.Undo.end()
def cutting():
    sequence = hiero.ui.activeSequence()
    if not sequence:
        print("No active sequence found!")
        return
    
    subtitle_track = None
    for track in sequence.videoTracks():
        if track.name() == "Subtitles":
            subtitle_track = track
            break
    sub_trackitems = subtitle_track.subTrackItems()[0]
    nuke.Undo.begin("cutting")
    for subs in sub_trackitems:
            sequence.razorAt(subs.timelineIn())
            sequence.razorAt(subs.timelineOut()+1)
    nuke.Undo.end()
    nuke.Undo.begin("deleting unnessary parts")
    for v_track in sequence.videoTracks():
        if v_track.name() == "Subtitles":
            continue
        for a_track in sequence.audioTracks():
            for v_item in v_track.items():
                for a_item in a_track.items():
                    if (v_item.timelineIn() == a_item.timelineIn() and v_item.timelineOut() == a_item.timelineOut() and not v_item.isLinked(a_item)) and v_item.source() == a_item.source() and v_item.source().mediaSource() == a_item.source().mediaSource():
                        v_item.link(a_item)
                        break
    for track in sequence.videoTracks() + sequence.audioTracks():
        if track.name() == "Subtitles":
            continue
        for item in track.items():
            matched = False
            for subs in sub_trackitems:
                if subs.timelineIn() == item.timelineIn() and item.timelineOut() == subs.timelineOut():
                    matched = True
                    break
            if not matched:
                track.removeItem(item)
    for track in sequence.videoTracks() + sequence.audioTracks():
        if track.name() == "Subtitles":
            origIn = track.subTrackItems()[0][0].timelineIn()
            track.subTrackItems()[0][0].setTimelineIn(0)
            track.subTrackItems()[0][0].setTimelineOut(track.subTrackItems()[0][0].timelineOut() - origIn)
        else:
            origIn = track.items()[0].timelineIn()
            track.items()[0].setTimelineIn(0)
            track.items()[0].setTimelineOut(track.items()[0].timelineOut() - origIn)
    for i in range(len(sub_trackitems)-1):
        gap = sub_trackitems[i+1].timelineIn() - sub_trackitems[i].timelineOut()
        sub_trackitems[i+1].setTimelineIn(sub_trackitems[i+1].timelineIn() - gap + 1)
        sub_trackitems[i+1].setTimelineOut(sub_trackitems[i+1].timelineOut() - gap + 1)
        ntin = 0
        for track in sequence.videoTracks() + sequence.audioTracks():
            if track.name() == "Subtitles" or ntin == track.items()[i+1].timelineIn():
                continue
            if i >= len(track.items()):
                break
            ntin = track.items()[i+1].timelineIn() - gap + 1
            track.items()[i+1].setTimelineIn(ntin)
            track.items()[i+1].setTimelineOut(track.items()[i+1].timelineOut() - gap + 1)
    nuke.Undo.end()
def shaker():
    active_seq = hiero.ui.activeSequence()
    selection = hiero.ui.getTimelineEditor(active_seq).selection()[0]
    track = selection.parent()

    frame_rate = active_seq.framerate().toInt()
    duration_frames = QInputDialog.getInt(None,"select the duration of vibration","Duration(sec)", 0)
    duration_frames = duration_frames[0] * frame_rate
    
    shake_intensity = QInputDialog.getInt(None,"select the intensity of vibration","Intensity", 20)
    shake_frequency = QInputDialog.getInt(None,"select the frequency of vibration","Frequency", 4)
    
    start_frame = selection.timelineIn()
    end_frame = start_frame + duration_frames
    
    frames_per_shake = int(frame_rate / shake_frequency[0])
    num_keyframes = int(duration_frames / frames_per_shake) + 1

    nuke.Undo.begin("adding shake effect")
    placing = len(track.subTrackItems())
    translate_effect = track.createEffect(effectType="Transform",trackItem=selection,subTrackIndex=placing)
    translate_node = translate_effect.node()
    traslate_knob = translate_node["translate"]
    traslate_knob.setAnimated()   
    for i in range(num_keyframes):
        durframe = i * frames_per_shake
        if durframe <= duration_frames:
            frame = start_frame + durframe
            x_offset = random.uniform(-shake_intensity[0], shake_intensity[0])
            y_offset = random.uniform(-shake_intensity[0], shake_intensity[0])
            traslate_knob.setValueAt(x_offset,frame,0)
            traslate_knob.setValueAt(y_offset,frame,1)
    traslate_knob.setValueAt(0,end_frame + 1, 0)
    traslate_knob.setValueAt(0,end_frame + 1, 1)
    nuke.Undo.end()

def splitsequences():
    clipbin = hiero.core.projects()[0].clipsBin()
    sequence = hiero.ui.activeSequence()
    endings = []
    for track in sequence.videoTracks():
        for item in track.items():
            if item.name() == "main" or item.name() == "mainphone":
                endings.append([item,sequence.name()])
    pending = None
    for i,ending in enumerate(endings):
        nsequence = hiero.core.Sequence(ending[1] + "_" + str(i))
        nsequence.changeFramerateKeepFrames(30)
        clipbin.addItem(hiero.core.BinItem(nsequence))
        Indist = None
        vidtrack = 0
        audtrack = 0
        for track in sequence.videoTracks() + sequence.audioTracks():
            add_track = None
            if "Video" in track.toString():
                add_track = hiero.core.VideoTrack("vid" + str(vidtrack))
                nsequence.addTrack(add_track)
                if vidtrack >= 1:
                    add_track.setBlendEnabled(True)
                    add_track.setBlendMaskEnabled(True) 
                vidtrack = vidtrack + 1
            else:
                add_track = hiero.core.AudioTrack("aud" + str(audtrack))
                audtrack = audtrack + 1
                nsequence.addTrack(add_track)
            for item in track.items():
                if item.timelineIn() <= ending[0].timelineIn() and (pending is None or item.timelineIn()>pending[0].timelineOut()):
                    item_clone = item.copy()
                    add_track.addTrackItem(item_clone)
                    if Indist is None:
                        Indist = item.timelineIn()
                    if Indist != 0:                        
                        item_clone.setTimelineIn(item_clone.timelineIn() - Indist)
                        item_clone.setTimelineOut(item_clone.timelineOut() - Indist)
            if "Video" in track.toString() and len(track.subTrackItems()) != 0:
                for j in range(len(track.subTrackItems())):
                    for sub in track.subTrackItems()[j]:
                        if sub.timelineIn() <= ending[0].timelineIn() and (pending is None or sub.timelineIn()>pending[0].timelineOut()):
                            cloned_sub = sub.copy()
                            add_track.addSubTrackItem(cloned_sub,j)
                            if Indist != 0:
                                cloned_sub.setTimelineIn(cloned_sub.timelineIn() - Indist)
                                cloned_sub.setTimelineOut(cloned_sub.timelineOut() - Indist)
            if "Video" in track.toString() and len(add_track.items()) == 0 and len(add_track.subTrackItems()) > 0:
                add_track.setName("Subtitles")
        pending = ending

def groupsequencer():
    global cvbin
    cselection = cvbin.selection()
    clipbin = hiero.core.projects()[0].clipsBin()
    #nsequences = []
    hiero.core.openProject("~/editables/saves/endings/endings.hrox")
    endproject = hiero.core.projects()[-1]
    endseq = endproject.sequences("youtube")[1]
    for k in range(len(endseq.videoTracks())):
        for item in endseq.videoTracks()[k].items():
            ifbined = False
            for bin in clipbin.clips():
                if item.source().mediaSource() == bin.activeItem().mediaSource():
                    ifbined = True
                    break
            if not ifbined:
                item_c = item.copy()
                clipbin.addItem(item_c.currentVersion().parent())
    for k in range(len(endseq.audioTracks())):
        for item in endseq.audioTracks()[k].items():
            ifbined = False
            for bin in clipbin.clips():
                if item.source().mediaSource() == bin.activeItem().mediaSource():
                    ifbined = True
                    break
            if not ifbined:
                item_c = item.copy()
                clipbin.addItem(item_c.currentVersion().parent())
    for select in cselection:
        sequence = select.activeItem() 
        endings = []
        for track in sequence.videoTracks():
            if track.name() == "Subtitles":
                subtrack = track
                break
            """for item in track.items():
                if item.name() == "main" or item.name() == "mainphone":
                    endings.append([item,sequence.name()])"""
        for sub in subtrack.subTrackItems()[0]:
            if sub.node()['message'].value() != '':
                endings.append([sub.timelineIn(), sub.timelineOut(),sub.node()['message'].value().replace(' ',"-"),sequence.name()])
            else:
                endings.append([sub.timelineIn(), sub.timelineOut(),sub.name(),sequence.name()])
        for i,ending in enumerate(endings):
            #nsequence = hiero.core.Sequence(ending[2] + "_" + str(i))
            nsequence = hiero.core.Sequence(ending[3] + "_" + str(i) + "_" + ending[2])
            nsequence.changeFramerateKeepFrames(30)
            clipbin.addItem(hiero.core.BinItem(nsequence))
            Indist = None
            vidtrack = 0
            audtrack = 0
            for track in sequence.videoTracks() + sequence.audioTracks():
                add_track = None
                if "Video" in track.toString():
                    add_track = hiero.core.VideoTrack("vid" + str(vidtrack))
                    nsequence.addTrack(add_track)
                    if vidtrack >= 1:
                        add_track.setBlendEnabled(True)
                        add_track.setBlendMaskEnabled(True) 
                    vidtrack = vidtrack + 1
                else:
                    add_track = hiero.core.AudioTrack("aud" + str(audtrack))
                    audtrack = audtrack + 1
                    nsequence.addTrack(add_track)
                for item in track.items():
                    if item.timelineIn() >= ending[0] and item.timelineOut() <= ending[1]:
                        item_clone = item.copy()
                        add_track.addTrackItem(item_clone)
                        #else:
                            #add_track.addTrackItem(item_clone,add_track.items()[len(add_track.items())-1].timelineOut())
                        if Indist is None:
                            Indist = item.timelineIn()
                        if Indist != 0:                        
                            item_clone.setTimelineIn(item_clone.timelineIn() - Indist)
                            item_clone.setTimelineOut(item_clone.timelineOut() - Indist)
                if "Video" in track.toString() and len(track.subTrackItems()) != 0:
                    for j in range(len(track.subTrackItems())):
                        for sub in track.subTrackItems()[j]:
                            if sub.timelineIn() >= ending[0] and sub.timelineOut() <= ending[1]:
                                cloned_sub = sub.copy()
                                add_track.addSubTrackItem(cloned_sub,j)
                                if Indist != 0:
                                    cloned_sub.setTimelineIn(cloned_sub.timelineIn() - Indist)
                                    cloned_sub.setTimelineOut(cloned_sub.timelineOut() - Indist)
                if "Video" in track.toString() and len(add_track.items()) == 0 and len(add_track.subTrackItems()) > 0:
                    add_track.setName("Subtitles")
                    add_track.removeSubTrackItem(add_track.subTrackItems()[0][0])
                    if len(add_track.subTrackItems()) == 0:
                        nsequence.removeTrack(add_track)
            outrotime = nsequence.videoTracks()[0].items()[len(nsequence.videoTracks()[0].items())-1].timelineOut()
            vidout = endseq.videoTracks()[0].items()[0].clone()
            vidout.setTimelineIn(vidout.timelineIn() + outrotime + 1)
            vidout.setTimelineOut(vidout.timelineOut() + outrotime + 1)
            nsequence.videoTracks()[0].addTrackItem(vidout)
            soundout1 = endseq.audioTracks()[0].items()[0].clone()
            soundout1.setTimelineIn(soundout1.timelineIn() + outrotime + 1)
            soundout1.setTimelineOut(soundout1.timelineOut() + outrotime + 1)
            soundout2 = endseq.audioTracks()[1].items()[0].clone()
            soundout2.setTimelineIn(soundout2.timelineIn() + outrotime + 1)
            soundout2.setTimelineOut(soundout2.timelineOut() + outrotime + 1)
            nsequence.audioTracks()[0].addTrackItem(soundout1)
            nsequence.audioTracks()[1].addTrackItem(soundout2)
        endproject.close()
def mobalize():
    indamount = QInputDialog.getInt(None,"select the number of video clips(from buttom to top) to be re-arranged","Amount", 1)
    global cvbin
    cselection = cvbin.selection()
    clipbin = hiero.core.projects()[0].clipsBin()
    #nsequences = []
    hiero.core.openProject("/home/madhatter/editables/saves/endings/endings.hrox")
    endproject = hiero.core.projects()[-1]
    endseq = endproject.sequences("tiktok")[0]
    for k in range(len(endseq.videoTracks())):
        for item in endseq.videoTracks()[k].items():
            ifbined = False
            for bin in clipbin.clips():
                if item.source().mediaSource() == bin.activeItem().mediaSource():
                    ifbined = True
                    break
            if not ifbined:
                item_c = item.copy()
                clipbin.addItem(item_c.currentVersion().parent())
    for k in range(len(endseq.audioTracks())):
        for item in endseq.audioTracks()[k].items():
            ifbined = False
            for bin in clipbin.clips():
                if item.source().mediaSouclrce() == bin.activeItem().mediaSource():
                    ifbined = True
                    break
            if not ifbined:
                item_c = item.copy()
                clipbin.addItem(item_c.currentVersion().parent())
    for select in cselection:
        break_count = 0
        nsequence = select.activeItem().copy()
        nsequence.setName(select.activeItem().name() + "_mobile")
        clipbin.addItem(hiero.core.BinItem(nsequence))
        nsequence.setFormat(hiero.core.Format(1080,1920,1,"mobile_std"))
        subtrack=None
        allvidtracks = []
        for track in nsequence.videoTracks():
            if track.name() == "Subtitles":
                subtrack = track
            else:
                allvidtracks.append(track)
            nsequence.removeTrack(track)
            copyvids = []
        backtrack = hiero.core.VideoTrack("background")
        nsequence.addTrack(backtrack)
        backdrop = hiero.core.VideoTrack("background_drop")
        nsequence.addTrack(backdrop)
        backdrop.setBlendEnabled(True)
        backdrop.setBlendMaskEnabled(True)
        seamtrack = hiero.core.VideoTrack("seam")
        nsequence.addTrack(seamtrack)
        seamtrack.setBlendEnabled(True)
        seamtrack.setBlendMaskEnabled(True)
        sigiltrack = hiero.core.VideoTrack("sigil")
        nsequence.addTrack(sigiltrack)
        sigiltrack.setBlendEnabled(True)
        sigiltrack.setBlendMaskEnabled(True)
        for ind,track in enumerate(allvidtracks):
            nsequence.addTrack(track)
            if ind < indamount[0]:
                copyvid = allvidtracks[ind].copy()
                nsequence.addTrack(copyvid)
                copyvid.setBlendEnabled(True)
                copyvid.setBlendMaskEnabled(True)
                copyvids.append(copyvid)
                for item in copyvid.items():
                    if item.name() == "main":
                        copyvid.removeItem(item)
                        break
        outtime = 0
        intime = 0
        uppertrack = None
        for i in range(indamount[0]):
            totalsubtrack = len(allvidtracks[i].subTrackItems()) - 1
            for j in range(len(allvidtracks[i].items())):
                allvidtracks[i].setBlendEnabled(True)
                allvidtracks[i].setBlendMaskEnabled(True)
                if allvidtracks[i].items()[j].name() == "main":
                    intime = allvidtracks[i].items()[j].timelineIn()
                    allvidtracks[i].removeItem(allvidtracks[i].items()[j])
                    for item in endseq.videoTracks()[0].items():
                        outtime = endseq.videoTracks()[0].items()[0].timelineOut() + intime
                        endcop = item.copy()
                        backtrack.addTrackItem(endcop)
                        endcop.move(intime)
                        endcop.setTimelineIn(0)
                        endcop.setSourceIn(endcop.sourceIn() - intime)
                        #endhandlein = endcop.handleInTime()
                        """if endhandlein > 0:
                            endcopd = endcop.handleInTime() - endcop.timelineIn() 
                            endcop.trimIn(endcopd)
                            endcopin = endcop.timelineIn() 
                            endcop = item.copy()
                            endcop.setTimelineIn(endcop.timelineOut() - endcopd)
                            endcop.setSourceIn(endcop.sourceIn() + endcopd)
                            endcop.move(endcopin - endcopd)
                            backtrack.addTrackItem(endcop)
                            endcopin = endcop.timelineIn()
                            endcop.move(0)
                            #endcop.setSourceIn(endcop.sourceIn() - endcopin)
                            #endcop.move(endcopin - (endcop.timelineOut() - endcop.timelineIn()))
                            #endhandlein = endcop.handleInTime()"""
                    for item in backtrack.items():
                        nitem = item.clone()
                        backdrop.addTrackItem(nitem)
                        cropeffect = backdrop.createEffect(effectType="Crop",trackItem=nitem,subTrackIndex=0)
                        gradeffect = backdrop.createEffect(effectType="Grade",trackItem=nitem,subTrackIndex=1)
                        cropeffect.node()["box"].setValue([0,1791,1080,1920])
                        gradeffect.node()["multiply"].setValue(0.3)
                    uppertrack = hiero.core.VideoTrack("upperanimation")
                    uppertrack.setBlendEnabled(True)
                    uppertrack.setBlendMaskEnabled(True)
                    nsequence.addTrack(uppertrack)
                    continue
                if allvidtracks[i].items()[j].name() == "break":
                    break_effect = allvidtracks[i].createEffect(effectType="Transform",trackItem=allvidtracks[i].items()[j],subTrackIndex=0)
                    break_effect.node()["center"].setValue([540,960])
                    break_effect.node()["translate"].setValue([60,-20])
                    break_effect.node()["scale"].setValue(1.75)
                    crop_effect = allvidtracks[i].createEffect(effectType="Crop",trackItem=allvidtracks[i].items()[j],subTrackIndex=1)
                    crop_effect.node()["box"].setValue([0,0,1080,1662.51])
                    copyvids[i].removeItem(copyvids[i].items()[j-break_count])
                    break_count += 1
                    continue

                translate_effect = allvidtracks[i].createEffect(effectType="Transform",trackItem=allvidtracks[i].items()[j],subTrackIndex=totalsubtrack+1)
                translate_effect_clone = translate_effect.copy()
                translate_effect.node()["translate"].setValue([-237,265])
                translate_effect.node()["center"].setValue([540,960])
                translate_effect.node()["scale"].setValue(0.81)
                translate_effect_clone.node()["invert_matrix"].setValue(True)
                translate_effect_clone.node()["translate"].setValue([-220,775])
                translate_effect_clone.node()["center"].setValue([540,960])
                translate_effect_clone.node()["scale"].setValue(1.37)
                copyvids[i].addSubTrackItem(translate_effect_clone,totalsubtrack+1)

        loopclip = find_name("output", clipbin)
        newloop = uppertrack.addTrackItem(loopclip,0)
        loopwarp = uppertrack.createEffect(effectType="TimeWarp",trackItem=newloop,subTrackIndex=0)
        loopwarp.node()["lookup"].setExpression("frame % 14")
        newloop.setTimelineOut(outtime)
        newloop.setSourceOut(outtime)
        looptranslate = uppertrack.createEffect(effectType="Transform",trackItem=newloop,subTrackIndex=1)
        looptranslate.node()["center"].setValue([540,960])
        looptranslate.node()["translate"].setAnimated()
        looptranslate.node()["translate"].setValueAt(0,intime,0)
        looptranslate.node()["translate"].setValueAt(768,intime,1)
        looptranslate.node()["translate"].setValueAt(0,outtime,0)
        looptranslate.node()["translate"].setValueAt(-420,outtime,1)
        looptranslate.node()["scale"].setAnimated()
        looptranslate.node()["scale"].setValueAt(0.122,intime)
        looptranslate.node()["scale"].setValueAt(1,outtime)
        uppertrack.razorAt(intime)
        lastloop = uppertrack.subTrackItems()[0][len(uppertrack.subTrackItems()[0])-1]
        lastnumber = intime % 14
        lastloop.node()["lookup"].setExpression(f"(((frame - {intime - 1}) * 1.6) + {lastnumber}) % 14")
        ifexists = find_name("blank", clipbin)
        if ifexists is None:
            new_media = clipbin.createClip("../../blank.png")
        else:
            new_media = ifexists
        social_track = hiero.core.VideoTrack("thanks_mult")
        nsequence.addTrack(social_track)
        blank_item = social_track.addTrackItem(new_media,intime)
        blank_item.setTimelineOut(outtime)
        blank_item.setTimelineIn(intime)
        thanks_effect = social_track.createEffect(effectType="Text2",trackItem=blank_item,subTrackIndex=0)
        thanks_effect_node = thanks_effect.node()
        thanks_effect_node["global_font_scale"].setAnimated()
        thanks_effect_node["global_font_scale"].setValueAt(0,intime)
        thanks_effect_node["global_font_scale"].setValueAt(1.45,outtime)
        thanks_effect_node["box"].setAnimated()
        thanks_effect_node["box"].setValueAt(0,intime,0)
        thanks_effect_node["box"].setValueAt(1620,intime,1)
        thanks_effect_node["box"].setValueAt(1080,intime,2)
        thanks_effect_node["box"].setValueAt(1920,intime,3)
        thanks_effect_node["box"].setValueAt(1370,outtime,1)
        thanks_effect_node["box"].setValueAt(1670,outtime,3)
        thanks_effect_node["message"].setValue("Thanks for watching!!!")
        thanks_effect_node["xjustify"].setValue(1)
        thanks_effect_node["yjustify"].setValue(0)
        thanks_effect_node["color"].setValue([1,1,1,1])
        thanks_effect_node["enable_shadows"].setValue(True)
        thanks_effect_node["shadow_distance"].setValue(21)
        thanks_effect_node["shadow_size"].setValue(0)
        thanks_effect_node["shadow_opacity"].setValue(0.7)
        thanks_effect_node["shadow_color"].setValue([0,0,0,1])

        thanks_effect_copy = thanks_effect.copy()
        thanks_effect_copy_node = thanks_effect_copy.node()
        thanks_effect_copy_node["shadow_distance"].setValue(5)
        thanks_effect_copy_node["shadow_size"].setValue(5)
        thanks_effect_copy_node["shadow_color"].setValue([1,1,1,1])

        social_track.addSubTrackItem(thanks_effect_copy,1)
        social_track.setBlendEnabled(True)
        social_track.setBlendMaskEnabled(True)
        social_track.setBlendMode('mult')
        social_track = social_track.copy()
        social_track.setName("thanks_diff")
        nsequence.addTrack(social_track)
        social_track.setBlendEnabled(True)
        social_track.setBlendMaskEnabled(True)
        social_track.setBlendMode('difference')

        ifexists = find_name("youtube", clipbin)
        if ifexists is None:
            new_media = clipbin.createClip("../../youtube.png")
        else:
            new_media = ifexists
        social_track = hiero.core.VideoTrack("youtube_diff")
        nsequence.addTrack(social_track)
        ytlogo_item = social_track.addTrackItem(new_media,0)
        ytlogo_item.setTimelineOut(outtime)
        ytlogo_item.setTimelineIn(0)
        yt_translate_effect = social_track.createEffect(effectType="Transform",trackItem=ytlogo_item,subTrackIndex=0)
        yt_translate_effect_node = yt_translate_effect.node()
        yt_translate_effect_node["translate"].setAnimated()
        yt_translate_effect_node["translate"].setValueAt(-450,intime,0)
        yt_translate_effect_node["translate"].setValueAt(766,intime,1)
        yt_translate_effect_node["translate"].setValueAt(-375,outtime,0)
        yt_translate_effect_node["translate"].setValueAt(140,outtime,1)
        yt_translate_effect_node["center"].setValue([540,960])
        yt_translate_effect_node["scale"].setAnimated()
        yt_translate_effect_node["scale"].setValueAt(0.12,intime)
        yt_translate_effect_node["scale"].setValueAt(0.22,outtime)
        yt_text_effect = social_track.createEffect(effectType="Text2",trackItem=ytlogo_item,subTrackIndex=1)
        yt_text_effect_node = yt_text_effect.node()
        yt_text_effect_node["global_font_scale"].setAnimated()
        yt_text_effect_node["global_font_scale"].setValueAt(0.71,intime)
        yt_text_effect_node["global_font_scale"].setValueAt(1.74,outtime)
        yt_text_effect_node["box"].setAnimated()
        yt_text_effect_node["box"].setValueAt(170,intime,0)
        yt_text_effect_node["box"].setValueAt(1646,intime,1)
        yt_text_effect_node["box"].setValueAt(500,intime,2)
        yt_text_effect_node["box"].setValueAt(1791,intime,3)
        yt_text_effect_node["box"].setValueAt(285,outtime,0)
        yt_text_effect_node["box"].setValueAt(1002,outtime,1)
        yt_text_effect_node["box"].setValueAt(1065,outtime,2)
        yt_text_effect_node["box"].setValueAt(1198,outtime,3)
        yt_text_effect_node["yjustify"].setValue(1)
        yt_text_effect_node["message"].setValue("@tasokait")
        yt_text_effect_node["color"].setValue([1,1,1,1])
        social_track.setBlendEnabled(True)
        social_track.setBlendMaskEnabled(True)
        social_track.setBlendMode('difference')

        ifexists = find_name("twitch", clipbin)
        if ifexists is None:
            new_media = clipbin.createClip("../../twitch-icon-511x512-qrwypaov.png")
        else:
            new_media = ifexists
        social_track = hiero.core.VideoTrack("twitch_minus")
        nsequence.addTrack(social_track)
        twitchlogo_item = social_track.addTrackItem(new_media,0)
        twitchlogo_item.setTimelineOut(outtime)
        twitchlogo_item.setTimelineIn(0)
        twitch_translate_effect = social_track.createEffect(effectType="Transform",trackItem=twitchlogo_item,subTrackIndex=0)
        twitch_translate_effect_node = twitch_translate_effect.node()
        twitch_translate_effect_node["translate"].setAnimated()
        twitch_translate_effect_node["translate"].setValueAt(440,intime,0)
        twitch_translate_effect_node["translate"].setValueAt(766,intime,1)
        twitch_translate_effect_node["translate"].setValueAt(380,outtime,0)
        twitch_translate_effect_node["translate"].setValueAt(340,outtime,1)
        twitch_translate_effect_node["center"].setValue([540,960])
        twitch_translate_effect_node["scale"].setAnimated()
        twitch_translate_effect_node["scale"].setValueAt(0.1,intime)
        twitch_translate_effect_node["scale"].setValueAt(0.22,outtime)
        twitch_text_effect = social_track.createEffect(effectType="Text2",trackItem=twitchlogo_item,subTrackIndex=1)
        twitch_text_effect_node = twitch_text_effect.node()
        twitch_text_effect_node["global_font_scale"].setAnimated()
        twitch_text_effect_node["global_font_scale"].setValueAt(0.71,intime)
        twitch_text_effect_node["global_font_scale"].setValueAt(1.74,outtime)
        twitch_text_effect_node["box"].setAnimated()
        twitch_text_effect_node["box"].setValueAt(590,intime,0)
        twitch_text_effect_node["box"].setValueAt(1646,intime,1)
        twitch_text_effect_node["box"].setValueAt(950,intime,2)
        twitch_text_effect_node["box"].setValueAt(1791,intime,3)
        twitch_text_effect_node["box"].setValueAt(35,outtime,0)
        twitch_text_effect_node["box"].setValueAt(1186,outtime,1)
        twitch_text_effect_node["box"].setValueAt(800,outtime,2)
        twitch_text_effect_node["box"].setValueAt(1381,outtime,3)
        twitch_text_effect_node["yjustify"].setValue(1)
        twitch_text_effect_node["xjustify"].setValue(1)
        twitch_text_effect_node["message"].setValue("@tasokait")
        twitch_text_effect_node["color"].setValue([1,1,1,1])
        social_track.setBlendEnabled(True)
        social_track.setBlendMaskEnabled(True)
        social_track.setBlendMode('minus')

        ifexists = find_name("sigil",clipbin)
        if ifexists is None:
            new_media = clipbin.createClip("../../endings/sigil_effect/sigil####.png")
        else:
            new_media = ifexists
        sigilitem = sigiltrack.addTrackItem(new_media,0)
        sigilitem.setTimelineOut(outtime)
        sigilitem.setSourceOut(outtime)
        sigilitem.setSourceIn(0)
        
        ifexists = find_name("seam",clipbin)
        if ifexists is None:
            new_media = clipbin.createClip("../../endings/seam_effect/seam####.png")
        else:
            new_media = ifexists
        seamitem = seamtrack.addTrackItem(new_media,0)
        seamitem.setTimelineOut(outtime)
        seamitem.setSourceOut(outtime)
        seamitem.setSourceIn(0)

        ifexists = find_name("Tasogare_VT_dare",clipbin)
        if ifexists is None:
            new_media = clipbin.createClip("../../emotes/Tasogare_VT_dare.png")
        else:
            new_media = ifexists
        social_track = hiero.core.VideoTrack("daretrack")
        nsequence.addTrack(social_track)
        social_track.setBlendEnabled(True)
        social_track.setBlendMaskEnabled(True)
        dareitem = social_track.addTrackItem(new_media,0)
        dareitem.setTimelineOut(outtime)
        dare_translate = social_track.createEffect(effectType="Transform",trackItem=dareitem,subTrackIndex=0)
        dare_translate.node()["translate"].setValue([-430,896])
        dare_translate.node()["scale"].setValue(0.116)
        dare_translate.node()["center"].setValue([540,960])

        ifexists = find_name("dance",clipbin)
        if ifexists is None:
            new_media = clipbin.createClip("../../emotes/dance.mov")
        else:
            new_media = ifexists
        social_track = hiero.core.VideoTrack("dancetrack")
        nsequence.addTrack(social_track)
        social_track.setBlendEnabled(True)
        social_track.setBlendMaskEnabled(True)
        newloop = social_track.addTrackItem(new_media,0)
        loopwarp = social_track.createEffect(effectType="TimeWarp",trackItem=newloop,subTrackIndex=0)
        loopwarp.node()["lookup"].setExpression("frame % 36")
        newloop.setTimelineOut(outtime)
        newloop.setSourceOut(outtime)
        looptranslate = social_track.createEffect(effectType="Transform",trackItem=newloop,subTrackIndex=1)
        looptranslate.node()["translate"].setValue([245,896])
        looptranslate.node()["scale"].setValue(0.117)
        looptranslate.node()["center"].setValue([540,960])

        if subtrack is not None:
            for i in range (2):
                for sub in subtrack.subTrackItems()[i]:
                    sub.node()["animation_layers"].setValue(-300,5)
                    sub.node()["animation_layers"].setValue(1,6)
                    sub.node()["animation_layers"].setValue(1,7)
                    sub.node()["box"].setValue([0,1250,1075,1400])
                    sub.node()["xjustify"].setValue(1)
                    sub.node()["yjustify"].setValue(1)
            nsequence.addTrack(subtrack)
        audrep = 0
        for audioTrack in nsequence.audioTracks():
            for item in audioTrack.items():
                if item.name() == "myvideo":
                    aind = item.timelineIn()
                    audioTrack.removeItem(item)
                    naudio = endseq.audioTracks()[0].items()[0].copy()
                    naudio.move(aind)
                    audioTrack.addTrackItem(naudio)
                    audrep = audrep + 1
                    break
            if audrep == 2:
                break
    endproject.close()
def bintrap(e):
    global cvbin
    if type(e.sender) is hiero.ui.BinView and cvbin is None:
        cvbin = e.sender
        hiero.core.events.unregisterInterest( hiero.core.events.EventType.kSelectionChanged, bintrap )

def find_name(name , clipbin: hiero.core.Bin):
    for clip in clipbin.clips():
        if name in clip.activeItem().toString():
            return clip.activeItem()
    return None 

def renderall():
    project = hiero.core.projects()[-1].bins("render")[0]

    exportObj = hiero.core.TimelineDirectExport()
    prores_export = {
        "Audio Codec" : "linear PCM (wav)",
        "Bit Depth" : "32 bit(float)",
        "Codec" : "Apple ProRes",
        "Codec Profile" : "ProRes 4:2:2 HQ 10-bit",
        "Data Range" : "Video Range",
        "Fast Start" : "True",
        "Include Audio" : "True",
        "Output Channels" : "stereo",
        "Reformat" : "None",
        "Sample Rate" : "48000 Hz",
        "Views" : "main",
        "Write Timecode" : "True",
        "YCbCr Matrix" : "Rec 709",
        "colorspace" : "default",
        "ocioDisplay" : "default",
        "ocioView" : "sRGB",
        "transformType" : "colorspace",
        "Include Annotations" : "False",
        "Color Primaries" : "BT.709 (Rec 709)",
        "Transfer Function" : "BT.709 (Rec 709)",
        "output transform" : "rec709"
    }

    for sequence in project.sequences():
        mname = sequence.name()
        mname = mname + ".mov"
        exportObj.exportSequence(sequence.activeItem(), os.path.join("~/editables/export/cache/", mname), prores_export)