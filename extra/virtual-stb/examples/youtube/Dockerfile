FROM stbtester/stb-tester-virtual-stb:latest

MAINTAINER will@stb-tester.com

RUN sudo apt-get update && sudo apt-get install -y chromium-browser

RUN mkdir -p /var/lib/stbt/.config/chromium/Default/
ADD Preferences /var/lib/stbt/.config/chromium/Default/Preferences

CMD chromium-browser --no-sandbox --app=https://www.youtube.com/tv#/
