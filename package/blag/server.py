#!/usr/bin/env python3

import datetime
import os
import re
import socket
import urllib.parse

from cc_pathlib import Path

import cherrypy

import oaktree

import oaktree.proxy.html5
import oaktree.proxy.braket

import marccup

import marccup.parser.page
import blag.composer

blag_root_dir = Path(os.environ["BLAG_root_DIR"])
blag_content_dir = Path(os.environ["BLAG_content_DIR"])
blag_static_dir = Path(os.environ["BLAG_static_DIR"])

def pagekey_to_datetime(t) :
	return datetime.datetime.strptime(t, '%Y%m%d_%H%M')

def html_format(txt, * pos, ** nam) :
	for i, p in enumerate(pos) :
		txt = txt.replace(f'${{{i}}}', p)
	for k, v in nam.items() :
		txt = txt.replace(f'${{{k}}}', v)
	return txt

def authenticated_page(func) :
	def app(* pos, ** nam) :
		print(pos, nam)
		if 'meeple' in cherrypy.session :
			return func(* pos, ** nam)
		else :
			raise cherrypy.HTTPRedirect("/login")
	return app

class BlagServer() :

	month_lst = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']
	weekday_lst = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']

	mime_map = {
		'.png': "image/png",
	}

	def __init__(self, content_dir) :
		self.content_dir = content_dir

		self.info = (self.content_dir / "info.json").load()
		self.meeple = (self.content_dir / "meeple.json").load()

		self.scan()

	def scan(self) :
		# check the folder for new content
		page_rec = re.compile(r'^(?P<key>\d{8}_\d{4}).(?P<title>.*?)$')
		
		page_map = dict()
		for pth in self.content_dir :
			page_res = page_rec.match(pth.name)
			if pth.is_dir() and page_res is not None and (pth / 'content.mcp').is_file() :
				page_map[page_res.group('key')] = page_res.group('title')

		self.page_map = page_map

	def pkey_to_content(self, page) :
		if page in self.page_map :
			fnm = f'{page}.{urllib.parse.quote(self.page_map[page])}'
			pth = self.content_dir / fnm
			if pth.is_dir() and (pth / 'content.mcp').is_file() :
				return (pth / 'content.mcp')
		print("----", self.page_map, fnm, pth, pth.is_dir())
		raise ValueError(f'{page} is not a known page')

	def pkey_to_folder(self, pkey) :
		""" the pkey consists only of the first 13 characters"""
		if pkey in self.page_map :
			return self.content_dir / f'{pkey}.{self.page_map[pkey]}'
		raise ValueError(f'{pkey} is not a known page')

	def pkey_to_header(self, pkey) :
		if pkey in self.page_map :
			title = urllib.parse.unquote(self.page_map[pkey])
			date = datetime.datetime.strptime(pkey, '%Y%m%d_%H%M')
			return f"{self.weekday_lst[date.weekday()]} {date.day} {self.month_lst[date.month -1]} {date.year} 〜 {title}"
		raise ValueError(f'{pkey} is not a known page')

	@cherrypy.expose
	# @authenticated_page
	def index(self, * pos, ** nam) :

		template = (blag_static_dir / 'html' / 'index.html').read_text()

		if 'page' not in nam :
			raise cherrypy.HTTPRedirect('chrono')
		
		m = ( self.pkey_to_folder(nam['page']) / 'content.mcp' ).read_text()
		cherrypy.session['page'] = nam['page']

		u = marccup.parser.page.PageParser()
		o = u.parse(m)
		b = oaktree.proxy.braket.BraketProxy(indent='\t')

		b.save(o, self.pkey_to_folder(nam['page']) / 'content.bkt')

		c = blag.composer.Html5Composer().compose(o)

		h = oaktree.proxy.html5.Html5Proxy(indent='\t', fragment=True)
		h.save(c.sub[0], self.pkey_to_folder(nam['page']) / 'content.html')

		h = oaktree.proxy.html5.Html5Proxy(indent=None, fragment=True)
		t = h.save(c.sub[0])

		return html_format(template, article=t, header=self.pkey_to_header(nam['page']), ** self.info)

	@cherrypy.expose
	def login(self, * pos, ** nam) :
		s = list()
		w = s.append

		w('<p>')
		w('<select name="user_select">')
		w(f'<option name="__unknown__">la grenouille avec une grande bouche</option>')
		for mp in sorted(self.meeple) :
			w(f'<option name="user_{mp}">{mp}</option>')
		w(f'</select>')
		w('</p><p>')
		w('<select name="day_select">')
		for d in range(31) :
			w(f'<option name="day_{d+1}">{d+1}</option>')
		w(f'</select>')

		w('<select name="month_select">')
		for m in self.month_lst :
			w(f'<option name="month_{m}">{m}</option>')
		w(f'</select>')
		w('</p>')

		txt = (blag_static_dir / 'html' / 'login.html').read_text()
		return html_format(txt, login='\n'.join(s), ** self.info)

	@cherrypy.expose
	def _login_validate(self, * pos, ** nam) :
		print(pos, nam)
		if 'user_select' in nam :
			user = nam['user_select']
			if user in self.meeple :
				day = int(nam['day_select'])
				month = self.month_lst.index(nam['month_select']) + 1
				print([month, day], self.meeple[user][1:])
				if [month, day] == self.meeple[user][1:] :
					print("et la bobinette etc.")
					cherrypy.session['meeple'] = user
		
		raise cherrypy.HTTPRedirect('/index')

	@cherrypy.expose
	def chrono(self, * pos, ** nam) :
		s = ['<table id="chrono">\n<tbody>',]
		for pk in reversed(sorted(self.page_map)) :
			title = self.page_map[pk]
			s.append(f'<tr data-pagekey="{pk}"><td class="chrono_datetime">{pagekey_to_datetime(pk):%Y.%m.%d %H:%M}</td><td class="chrono_title">{title}</td></tr>')
		s.append('</tbody>\n</table>')

		txt = (blag_static_dir / 'html' / 'chrono.html').read_text()
		return html_format(txt, chrono='\n'.join(s), ** self.info)

	@cherrypy.expose
	def img(self, * pos, ** nam) :
		pth_lst = list()
		if 'page' in cherrypy.session :
			pth_lst.append( self.pkey_to_folder(cherrypy.session['page']) / pos[0] )
		pth_lst.append( self.content_dir / "_img" / pos[0] )
		print(pth_lst)
		for pth in pth_lst :
			if pth.is_file() and pth.suffix in self.mime_map :
				cherrypy.response.headers['Content-Type'] = self.mime_map[pth.suffix]
				print("img", pos, nam)
				return pth.read_bytes()

if __name__ == '__main__' :

	cherrypy.config.update({
		'server.socket_host': socket.getfqdn(),
		'server.socket_port': 42009,
	})
		
	server_config = {
		'/': {
			'tools.staticdir.root': str(blag_root_dir),
			'tools.sessions.on': True,
		},
		'/_static' : {
			'tools.staticdir.on': True,
			'tools.staticdir.dir': "static",
		}
	}

	cherrypy.tree.mount(BlagServer(blag_content_dir), '/', config=server_config)

	cherrypy.engine.start()
	cherrypy.engine.block()
