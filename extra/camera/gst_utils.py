from gi.repository import Gst, GObject
import sys


Gst.init([])


class PipelineRunner:
    """Provides an easy way to run a pre-constructed Gstreamer pipeline much
    like gst-launch"""
    def __init__(self, pipeline, stop_pos=None):
        self.mainloop = GObject.MainLoop()
        self.err, self.dbg = None, None

        def on_error(_bus, message):
            self.err, self.dbg = message.parse_error()
            self.mainloop.quit()

        def on_warning(_bus, message):
            assert message.type == Gst.MessageType.WARNING
            _err, _dbg = message.parse_warning()
            sys.stderr.write("Warning: %s: %s\n%s\n" % (_err, _err.message, _dbg))

        def on_segment_done(_bus, _message):
            pipeline.send_event(Gst.Event.new_eos())
            pipeline.get_by_name('encoder').send_event(Gst.Event.new_eos())
            pipeline.get_by_name('audioenc').send_event(Gst.Event.new_eos())
            pipeline.get_by_name('mux').send_event(Gst.Event.new_eos())

        def on_eos(_bus, _message):
            pipeline.set_state(Gst.State.NULL)
            self.mainloop.quit()
        bus = pipeline.get_bus()

        # FIXME: For some reason bus.connect doesn't seem to work.  Have to use
        #        bus_callback instead.
        # bus.connect("message::eos", on_eos)
        # bus.connect("message::segment-done", segment_done)
        # bus.connect("message::error", on_error)
        # bus.connect("message::warning", on_warning)
        def bus_callback(bus, message, _data):
            if message.type == Gst.MessageType.SEGMENT_DONE:
                on_segment_done(bus, message)
            elif message.type == Gst.MessageType.ERROR:
                on_error(bus, message)
            elif message.type == Gst.MessageType.WARNING:
                on_warning(bus, message)
            elif message.type == Gst.MessageType.EOS:
                on_eos(bus, message)
            return True
        bus.add_watch(0, bus_callback, None)
        pipeline.set_state(Gst.State.PAUSED)

        if stop_pos is not None:
            pipeline.seek(
                1.0, Gst.Format.TIME, Gst.SeekFlags.SEGMENT | Gst.SeekFlags.FLUSH |
                Gst.SeekFlags.ACCURATE, Gst.SeekType.SET, 0, Gst.SeekType.SET,
                stop_pos)

        pipeline.set_state(Gst.State.PLAYING)
        self.pipeline = pipeline

    def run(self):
        self.mainloop.run()
        if self.err is not None:
            raise RuntimeError("Error running pipeline: %s\n\n%s" %
                               (self.err, self.dbg))

    def __del__(self):
        self.pipeline.set_state(Gst.State.NULL)
        self.pipeline.get_state(0)


def run_pipeline(pipeline, stop_pos=None):
    PipelineRunner(pipeline, stop_pos).run()


def _appsrc_push_data(appsrc, data, pts=0, duration=0):
    buf = Gst.Buffer.new_wrapped(data)
    buf.pts = pts
    buf.duration = duration
    appsrc.emit('push-buffer', buf)


def generate_svg_video(outfilename, svg_generator, caps="image/svg", container="ts"):
    """Makes it convenient to generate videos from a series of SVGs.  Pass in
    a generator which returns tuples of (frame duration, svg text)."""
    muxer = {'ts': 'mpegtsmux', 'mp4': 'mp4mux'}[container]
    pipeline = Gst.parse_launch("""
        appsrc name=videosrc format=time caps=%s,framerate=(fraction)25/1 !
            queue ! decodebin ! videoconvert ! videorate ! queue !
            avenc_mpeg4 bitrate=3000000 ! mpeg4videoparse ! queue ! mux.
        appsrc name=audiosrc format=time
            caps=audio/x-raw,format=S16LE,channels=2,rate=48000,layout=interleaved !
            audioconvert ! queue ! voaacenc ! aacparse ! queue ! mux.
        %s name=mux ! queue ! filesink location="%s" """ %
        (caps, muxer, outfilename))

    vsrc = pipeline.get_by_name('videosrc')
    asrc = pipeline.get_by_name('audiosrc')

    r = PipelineRunner(pipeline)

    t = 0
    for svg, duration in svg_generator:
        _appsrc_push_data(vsrc, svg, t, duration)
        _appsrc_push_data(asrc, '\0\0\0\0' * int(duration*48000/Gst.SECOND), t,
                          duration)
        t += duration

    _appsrc_push_data(vsrc, svg, t, 0)

    vsrc.emit("end-of-stream")
    asrc.emit('end-of-stream')

    r.run()
    return 0


def png2mp4(png, mp4, duration=60, container="ts"):
    return generate_svg_video(mp4, [(open(png).read(), duration*Gst.SECOND)],
                              'image/png', container=container)
