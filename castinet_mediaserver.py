#!/usr/bin/env python

import os
import sys
import cgi
import stat
import time
import glob
import json
import socket
import urllib
import tempfile
import subprocess

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

import CGIHTTPServer
import SocketServer

PORT = 8080
SERVE_DIR='/home/mkubilus/Software/pyblog/myblog'

convert_list = [".avi", ".flv", ".mkv", ".mpg"]
video_list = [".mp4",]
css=None

class MyTCPServer(SocketServer.ForkingTCPServer):
    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        SocketServer.ForkingTCPServer.server_bind(self)

class MyRequestHandler(CGIHTTPServer.CGIHTTPRequestHandler):
    def do_GET(self):
        print self.path
        root, ext = os.path.splitext(self.path)
        print "EXT:", ext
        # Get the local file location
        localpath = urllib.unquote(self.path).lstrip('/')

        if ext in convert_list:
            try: 
                # Send the headers
                self.send_response(200)
                self.send_header('Content-type', 'video/mp4')
                self.end_headers()
                
                # Transcode on the fly
                p0 = subprocess.Popen(
                    #['ffmpeg', '-i', localpath, '-vcodec', 'libvpx',
                    #    '-cpu-used', '5', '-deadline', 'realtime', '-s',
                    #    '640x360', '-f', 'webm', 'pipe:1'
                    #], stdout=subprocess.PIPE
                    ['ffmpeg', '-i', localpath, '-vcodec', 'libvpx',
                        '-vb', '1M', '-acodec', 'libvorbis',
                        '-deadline', 'realtime', '-s',
                        '640x360', '-f', 'webm', 'pipe:1'
                    ], stdout=subprocess.PIPE
                )
                
                time.sleep(1)

                # Read the piped data
                data = p0.stdout.read(1024)
                while p0.poll() is None:
                    self.wfile.write(data)
                    #print "wrote 1024 bytes"
                    data = p0.stdout.read(1024)

            finally:
                p0.terminate()
        elif (ext == '.png') and (not
                os.path.isfile(localpath)):
            print "LOCALPATH:", localpath 
            localdir = os.path.dirname(localpath)
            #print "GLOBS:", glob.glob("%s.*" % os.path.splitext(localpath)[0])
            vidfile=glob.glob("%s.*" %
                    os.path.splitext(localpath)[0].replace('[', '[[]'))[0]
            print "VIDFILE:", vidfile
            #vidpath = os.path.join(localdir, vidfile)
            vidpath = vidfile
            print "VIDPATH:", vidpath
            # Snag a picture
            p0 = subprocess.Popen(
                    ['ffmpeg', '-ss', '00:03:00', '-i',
                        vidpath,
                        '-vframes', '1', '-f', 'image2', 'pipe:1'],
                    stdout=subprocess.PIPE)
            data = p0.stdout.read()
            self.wfile.write(data)

        else:
            CGIHTTPServer.CGIHTTPRequestHandler.do_GET(self)

    def list_directory(self, path):
        """Helper to produce a directory listing (absent index.html).

        Return value is either a file object, or None (indicating an
        error).  In either case, the headers are sent, making the
        interface the same as for send_head().

        """
        dirlist=[]
        filelist=[]

        #try:
        if True:
            print "PATH:", path
            for item in os.listdir(path):
                print "CHECK PATH: ", item
                if os.path.isfile(os.path.join(path,item)):
                    filelist.append(item)
                elif os.path.isdir(os.path.join(path,item)):
                    dirlist.append(item)
        #except os.error:
        #    self.send_error(404, "No permission to list directory")
        #    print "some kind of error"
        #    return None

        filelist.sort(key=lambda a: a.lower())
        dirlist.sort(key=lambda a: a.lower())

        displaypath = cgi.escape(urllib.unquote(self.path))
        
        f = StringIO()
        f.write('<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">')
        f.write("<html>\n<title>Directory listing for %s</title>\n" % displaypath)
        #f.write("<head><style> td { padding-left: 2em; } \n")
        f.write('<head><style>')
        f.write(css)
        f.write('</style></head>')
        #f.write("th { padding-left: 2em; } </style></head> \n")
        f.write("<body>\n<h2>Directory listing for %s</h2>\n" % displaypath)
        f.write("<hr>\n<table>\n")
        f.write("<tr><th></th><th></th><th ALIGN=left>Name</th><th>Size</th><th ALIGN=right>Date Modified</th></tr>\n")

        full_list = dirlist + filelist
        print "FULL LIST: ", full_list

        for name in full_list:
            f.write('<tr>\n')
            fullname = os.path.join(path, name)
            stats = os.stat(fullname)
            size = stats[stat.ST_SIZE]
            mtime = time.ctime(stats[stat.ST_MTIME])
            displayname = linkname = name
            # Append / for directories or @ for symbolic links
            if os.path.isdir(fullname):
                displayname = name + "/"
                linkname = name + "/"
            if os.path.islink(fullname):
                displayname = name + "@"
                # Note: a link to a directory displays with @ and links with /
            f.write('<td></td><td>')
            root,ext = os.path.splitext(urllib.quote(linkname))
            if ext in convert_list or ext in video_list:
                f.write('<img src="%s" width=100 height=50>' %
                        "%s.png" % root
                )

                #bname=os.path.basename(urllib.quote(linkname))
                #print "BNAME:", bname
                #imgurl=self.google_image(bname)
                #print "URL:", imgurl
                #f.write('<img src="%s" width=100 height=50>' %
                #        imgurl
                #)
                
            f.write('</td><td><a href="%s">%s</a></td>\n'
                    % (urllib.quote(linkname), cgi.escape(displayname)))
            f.write('<td>%s</td><td>%s</td>' % (size, mtime))
        f.write("</table>\n<hr>\n</body>\n</html>\n")
        length = f.tell()
        f.seek(0)

        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.send_header("Content-Length", str(length))
        self.end_headers()
        return f


    def google_image(self, search):
        #search = x.split()
        #search = '%20'.join(map(str, search))
        url = 'http://ajax.googleapis.com/ajax/services/search/images?v=1.0&q=%s&safe=off' % search
        search_results = urllib.urlopen(url)
        js = json.loads(search_results.read().decode('utf-8'))
        results = js['responseData']['results']
        for i in results: rest = i['unescapedUrl']
        return rest

if __name__ == "__main__":
    with open('css/main.css') as h:
        css = h.read()

    argc = len(sys.argv)
    if argc >= 2:
        path = sys.argv[1]
        os.chdir(path)
    if argc >= 3:
        PORT = int(sys.argv[2])

    print "Running from %s" % os.getcwd()

    name = ""
    handler = MyRequestHandler
    httpd = MyTCPServer((name, PORT), handler)
    httpd.server_name = name
    httpd.server_port = PORT

    os.putenv("HTTP_HOST","%s:%s" % (name, PORT))
    os.environ["HTTP_HOST"] = "%s:%s" %(name, PORT)
    print os.getenv("HTTP_HOST")

    print "Serving at port %s" % PORT
    httpd.serve_forever()
