#!/usr/bin/env python3

import oaktree

""" this class take a parsed marccup as an oaktree, and transform it into an html5 tree """

class AutomaticTitle() :
	def __init__(self, max_depth=6) :
		self.max_depth = max_depth
		self.reset()

	def __str__(self) :
		return '.'.join(str(i) for i in self.h if i != 0) + '.&nbsp;'

	def reset(self) :
		self.h =  [0,] * self.max_depth

	def increment(self, d) :
		self.h[d] += 1
		for i in range(d+1, 6) :
			self.h[i] = 0

class Html5Composer() :

	tr_map = {
		"paragraph" : "p",
		# "alinea" : "span",
		"table_row" : "tr",
		"page": "article",
		"highlighted": "em",
		"important": "strong"
	}

	def __init__(self, title_num=None) :
		# title num est le numero à partir du quel commencer sous la forme d'un tuple
		if title_num is None :
			self.title_num = None
		else :
			self.title_num = AutomaticTitle(title_num)

		self.gallery_lst = list()

	# def compose(self, src, dst) :
	# 	# print(f"convert({src}, {dst})")
	# 	if isinstance(src, str) :
	# 		dst.add_text(src)
	# 	else :
	# 		for src_sub in src.sub :
	# 			if isinstance(src_sub, str) :
	# 				dst.add_text(src_sub)
	# 			else :
	# 				if src_sub.tag in self.tr_map :
	# 					dst_sub = dst.grow(self.tr_map[src_sub.tag])
	# 					self.compose(src_sub, dst_sub)
	# 				elif hasattr(self, f"_compose_{src_sub.tag}") :
	# 					getattr(self, f"_compose_{src_sub.tag}")(src_sub, dst)
	# 				else :
	# 					dst_sub = dst.grow(src_sub.tag)
	# 					self.compose(src_sub, dst_sub)

	def compose(self, child_src, parent_dst=None) :

		if parent_dst is None :
			parent_dst = oaktree.Leaf('_tmp_')

		if isinstance(child_src, str) :
			parent_dst.add_text(child_src)
		else :
			if child_src.tag in self.tr_map :
				# just a translation, easy, let's do that !
				sub_dst = parent_dst.grow(self.tr_map[child_src.tag],
					style=set(child_src.style)
				)
				sub_continue = True
			elif hasattr(self, f"_compose_{child_src.tag}") :
				# it has it special function, let's call it !
				sub_dst, sub_continue = getattr(self, f"_compose_{child_src.tag}")(child_src, parent_dst)
			else :
				# nothing of the above, just translate as this
				sub_dst = parent_dst.grow(child_src.tag)
				sub_continue = True

			if child_src.ident is not None :
				sub_dst.ident = f"{child_src.tag}_{child_src.ident}"
				if child_src.tag in ['paragraph', 'alinea'] :
					sub_dst.style.add('spec')

			# print(child_src, sub_dst, sub_continue)
			if sub_continue :
				for sub_src in child_src.sub :
					self.compose(sub_src, sub_dst)

		return parent_dst

	def _compose_title(self, src, dst) :

		if self.title_num is None :
			depth = 1
			if src.parent.tag == 'section' and 'depth' in src.parent.nam :
				depth = int( src.parent.nam['depth'] )
			sub = dst.grow(f'h{depth}')
			return sub, True
		else :
			d = len(src.ancestor_lst) - 3

			self.title_num.increment(d)

			sub_dst = dst.grow(f'h{d+1}').add_text(str(self.title_num))

			return sub_dst, True

	def _compose_quote(self, src, dst) :
		if 'is_block' in src.flag :
			sub_dst = dst.grow('blockquote')
		else :
			sub_dst = dst.grow('q')
		return sub_dst, True

	def _compose_book(self, src, dst) :
		return dst, True

	def _compose_link(self, src, dst) :
		src_lst = [i.strip() for i in src.sub[0].split('|')]

		if src_lst[0].startswith('http') :
			sub_dst = dst.grow('a', nam={'href':src_lst[0]})
		else :
			sub_dst = dst.grow('a', nam={'class':'cross-link', 'href':src_lst[0]})

		if len(src_lst) > 1:
			sub_dst.add_text(src_lst[1])
		else :
			sub_dst.add_text(src_lst[0])

		return sub_dst, False

	def _compose_math(self, src, dst) :
		if 'is_block' in src.flag :
			sub_dst = dst.grow('p', style={'mcp-math',})
		else :
			sub_dst = dst.grow('span', style={'mcp-math',})

		sub_dst.add_text(''.join(src.sub))

		return sub_dst, False

	def _compose_img(self, src, dst) :
		sub_dst = dst.grow('img', nam={'src':f"img/{src.pos[0].strip()}"})
		sub_dst.nam = src.nam
		return sub_dst, False	

	def _compose_critical(self, src, dst) :
		sub_dst = dst.grow('span', style="mcp-critical")
		dst.add_text('\n') # retour à la ligne
		return sub_dst, True

	def _compose_alinea(self, src, dst) :
		sub_dst = dst.grow('span')
		dst.add_text('\n') # retour à la ligne
		return sub_dst, True

	def _compose_table_cell(self, src, dst) :
		if 'header' in src.flag :
			sub_dst = dst.grow('th')
		else :
			sub_dst = dst.grow('td')

		#for sub_src in src.sub :
		#	compose(sub_src, sub_dst)
			# sub_dst.add_text(''.join(src.sub))

		return sub_dst, True

	def _compose_img(self, src, dst) :
		i_map = {'src' : src.pos[0], 'alt': src.sub[0]}
		sub_dst = dst.grow('img', nam=i_map)
		self.gallery_lst.append(i_map)
		return sub_dst, False

	def _compose_gallery(self, src, dst) :
		sub_dst = dst.grow('p')
		sub_dst.style.add('mcp-gallery')
		for img in src.sub :
			if img.tag == 'img' :
				self._compose_img(img, sub_dst)
		return sub_dst, False