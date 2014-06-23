FROM ubuntu:14.04
MAINTAINER will@stb-tester.com

RUN sudo apt-get update && \
    sudo apt-get install -y lighttpd && \
    sudo apt-get clean
RUN sudo sed -i \
        -e 's,document-root.*,document-root = "/var/lib/stbt",g' \
        -e 's/port.*/port = 8000/g' \
        -e 's,pid-file.*,pid-file = "/run/lighttpd/lighttpd.pid",g' \
        /etc/lighttpd/lighttpd.conf && \
    sudo lighty-enable-mod dir-listing && \
    echo 'mimetype.assign += ( ".log" => "text/plain" )' |\
        sudo tee /etc/lighttpd/conf-enabled/mime.conf && \
    sudo mkdir /run/lighttpd && \
    sudo chown www-data:www-data /run/lighttpd

VOLUME /var/lib/stbt/results
EXPOSE 8000
USER www-data

CMD ["lighttpd", "-D", "-f", "/etc/lighttpd/lighttpd.conf"]
