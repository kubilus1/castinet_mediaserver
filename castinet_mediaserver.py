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

convert_list = [".avi", ".flv", ".mkv", ".mpg"]
video_list = [".mp4",]
allmedia_list = convert_list + video_list
css=None

class MyTCPServer(SocketServer.ForkingTCPServer):
    def server_bind(self):
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        SocketServer.ForkingTCPServer.server_bind(self)

class MyRequestHandler(CGIHTTPServer.CGIHTTPRequestHandler):
    def do_GET(self):
        print "Looking for:", self.path
        root, ext = os.path.splitext(self.path)
        # Get the local file location
        localpath = urllib.unquote(self.path).lstrip('/')

        DEVNULL = open(os.devnull, 'w')

        if ext in convert_list:
            try: 
                # Send the headers
                self.send_response(200)
                self.send_header('Content-type', 'video/mp4')
                self.end_headers()
                
                # Transcode on the fly
                p0 = subprocess.Popen(
                    ['ffmpeg', '-i', localpath, '-vcodec', 'libvpx',
                        '-vb', '1M', '-acodec', 'libvorbis',
                        '-deadline', 'realtime', '-s',
                        '640x360', '-f', 'webm', 'pipe:1'
                    ], stdout=subprocess.PIPE, stderr=DEVNULL
                )
               
                # Give transcoding a moment
                time.sleep(1)

                # Read the piped data
                data = p0.stdout.read(1024)
                while p0.poll() is None:
                    self.wfile.write(data)
                    data = p0.stdout.read(1024)
            finally:
                p0.terminate()
        
        elif (ext == '.vpng') and (not
                os.path.isfile(localpath)):
            localdir = os.path.dirname(localpath)
            globstr = "%s*[.avi|.mp4|.flv|.mpg|.mkv]" % os.path.splitext(localpath)[0].replace('[', '?').replace(']', '?')
            vidfile=glob.glob(globstr)[0]
            vidpath = vidfile
            
            # Snag a picture
            p0 = subprocess.Popen(['ffmpeg', '-i',
                        vidpath, '-ss', '15', 
                        '-vframes', '1', '-f', 'image2', 'pipe:1'],
                    stdout=subprocess.PIPE, stderr=DEVNULL)
            p0.wait()
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

        try:
            print "PATH:", path
            for item in os.listdir(path):
                if os.path.isfile(os.path.join(path,item)) and \
                        os.path.splitext(item)[1] in allmedia_list:
                    filelist.append(item)
                elif os.path.isdir(os.path.join(path,item)):
                    dirlist.append(item)
        except os.error:
            self.send_error(404, "No permission to list directory")
            return None

        filelist.sort(key=lambda a: a.lower())
        dirlist.sort(key=lambda a: a.lower())

        displaypath = cgi.escape(urllib.unquote(self.path))
        
        f = StringIO()
        f.write('<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">')
        f.write("<html>\n<title>Directory listing for %s</title>\n" % displaypath)
        f.write('<head><style>')
        f.write(css)
        f.write('</style>')
        f.write('<meta name="viewport" content="width=device-width" />')    
        f.write('</head>')
        f.write("<body>\n<h2>Directory listing for %s</h2>\n" % displaypath)
        

        full_list = dirlist + filelist
        for name in full_list:
            f.write("<div class='grid grid-pad'>")
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
            
            f.write("<div class='alink clear'>")
            f.write("<a href='%s'>\n"
                    % (urllib.quote(linkname))) 
            f.write("<div class='col-1-4'>")
            f.write("<div class='content'>")
            
            # Request a thumbnail ....
            root,ext = os.path.splitext(urllib.quote(linkname))
            if ext in convert_list or ext in video_list:
                f.write('<img src="%s" width=150 height=75>\n' %
                        "%s.vpng" % root
                )

            f.write("</div></div><div class='col-1-3'>")
            f.write("<div class='content'>")
            f.write(cgi.escape(displayname))
            f.write("</div></div></a>")
            f.write("</div>")    
            f.write("</div>\n")
                
        f.write("</body>\n</html>\n")
        length = f.tell()
        f.seek(0)

        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.send_header("Content-Length", str(length))
        self.end_headers()
        return f

if __name__ == "__main__":

    # This could be run on any directory so pull in the css now.
    with open('css/main.css') as h:
        css = h.read()
    with open('css/simplegrid.css') as h:
        css = css + h.read()

    argc = len(sys.argv)
    if argc >= 2:
        path = sys.argv[1]
        os.chdir(path)
    if argc >= 3:
        PORT = int(sys.argv[2])
    
    print "---------------------"
    print "Castinet Media Server"
    print "  Now serving %s" % os.getcwd()

    hostname = ""
    handler = MyRequestHandler
    httpd = MyTCPServer((hostname, PORT), handler)
    httpd.server_name = hostname
    httpd.server_port = PORT

    print "  at port %s" % PORT
    httpd.serve_forever()
