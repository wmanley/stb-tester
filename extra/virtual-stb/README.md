`stbt virtual-stb <command>` does the following:

* Run the specified application under a private X server.
* Modify your stbt configuration file so that `stbt run` will take its video
  input from that application and `stbt.press()` will send keypresses to that
  application.

Usage:

    stbt virtual-stb glxgears

    stbt virtual-stb chromium-browser --app=http://youtube.com/tv

    docker build -t youtube examples/youtube
    stbt virtual-stb --docker-image=youtube
