import hiero.ui
import hiero.core.events
from srt_importer import import_srt_subtitles, add_stroke, cutting, shaker, import_srt_subtitles_read, splitsequences, groupsequencer,mobalize,renderall,bintrap 

menu = hiero.ui.menuBar().addMenu("srt manager")
menu.addAction("Import SRT Subtitles", import_srt_subtitles)
menu.addAction("Import Readable SRT Subtitles", import_srt_subtitles_read)
menu.addAction("add stroke", add_stroke)
menu.addAction("cut the tracks", cutting)
menu.addAction("Shake it", shaker)
menu.addAction("split endings", splitsequences)
menu.addAction("split grouped endings", groupsequencer)
menu.addAction("tiktokify selected sequences", mobalize)
menu.addAction("render selected", renderall)
hiero.core.events.registerInterest(hiero.core.events.EventType.kSelectionChanged,bintrap)
print("SRT Subtitle menu added.")