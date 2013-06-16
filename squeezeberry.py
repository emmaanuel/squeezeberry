#! /usr/bin/python
#    Copyright 2013 - Emmanuel Cordente
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    See <http://www.gnu.org/licenses/> to get a copy of the GNU General 
#    Public License.

import urllib2
import simplejson
import RPi.GPIO as GPIO
from time import sleep
import threading
import subprocess
import gaugette.rotary_encoder

# Class qui gere toutes les communications avec le serveur squeezebox
class SqueezeBoxServer():

	def __init__(self, host="127.0.0.1", port=9000, player_id=""):
		self.host = host
		self.port = port
		self.server_url = "http://%s:%s/jsonrpc.js" % (self.host, self.port)
		self.player_id = player_id
		self.artists = self.query( "artists", 0, 9999)['artists_loop']
		self.radio_count = self.query( "favorites", "items")['count']
		self.artist_count = len(self.artists)
		
	def query(self, *args):
		params = simplejson.dumps({'id':1, 'method':'slim.request', 'params':[self.player_id, list(args)]})
		req = urllib2.Request(self.server_url, params)
		response = urllib2.urlopen(req)
		response_txt = response.read()
		return simplejson.loads(response_txt)['result']		
		
	def setVolume(self, volume):
		self.query("mixer", "volume", volume)
		
	def getArtists(self):
		return self.artists
		
	def getArtistsCount(self):
		return self.artist_count
	
	def getRadiosCount(self):
		return self.radio_count
	
	def playRadio(self, radio):
		return self.query("favorites", "playlist", "play", "item_id:"+str(radio))
		
	def getArtistAlbum(self, artist_id):
		return self.query("albums", 0, 99, "tags:al", "artist_id:"+str(artist_id))['albums_loop']
		
	def playAlbum(self, id):
		return self.query("playlistcontrol", "cmd:load", "album_id:"+str(id))
		
	def pause(self):
			return self.query("pause")
	
	def previousSong(self):
		return self.query("playlist", "index", "-1")

	def nextSong(self):
		return self.query("playlist", "index", "+1")

	def getCurrentSongTitle(self):
		return self.query("current_title", "?")['_current_title']

	def getCurrentRadioTitle(self, radio):
		return self.query("favorites", "items", 0, 99)['loop_loop'][radio]['name']
	


############################
# Class de controle du LCD #
############################
class HD44780(threading.Thread):
	######################
	# Variable Shared    #
	######################
	_PULSE = 0.00005
	_DELAY = 0.00005

	######################
	# Constructeur       #
	######################
	def __init__(self, pin_rs=26, pin_e=24, pins_db=[22, 18, 16, 12], lcd_width=32):
		self.message = ""
		self.currentmessage = "azertyuiop"
		self.stop = False
		self.lcd_width = lcd_width
		self.pin_rs = pin_rs
		self.pin_e = pin_e
		self.pins_db = pins_db
		self.updating=False
		GPIO.setmode(GPIO.BOARD) 				# Use RaspPI GPIO numbers
		GPIO.setup(self.pin_e, GPIO.OUT)
		GPIO.setup(self.pin_rs, GPIO.OUT)
		for pin in self.pins_db:
			GPIO.setup(pin, GPIO.OUT)

		self.Clear()
		threading.Thread.__init__(self)

	######################
	# Demarrage du Thread# 
	######################
	def run(self):
		while self.stop == False:
			if self.message != self.currentmessage:
				self.currentmessage = self.message
				self.LcdMessage()
			sleep(0.005)

	######################
	# Arret du Thread    # 
	######################	
	def Stop(self):
		self.stop = True

	######################
	# Initialisation LCD # 
	######################
	def Clear(self):
		""" Blank / Reset LCD """
		self.LcdByte(0x33, False) # $33 8-bit mode
		self.LcdByte(0x32, False) # $32 8-bit mode
		self.LcdByte(0x28, False) # $28 8-bit mode
		self.LcdByte(0x0C, False) # $0C 8-bit mode
		self.LcdByte(0x06, False) # $06 8-bit mode
		self.LcdByte(0x01, False) # $01 8-bit mode

	######################
	#Execution sur le LCD# 
	######################
	def LcdByte(self, bits, mode):
		""" Send byte to data pins """
		# bits = data
		# mode = True  for character
		#        False for command

		GPIO.output(self.pin_rs, mode) # RS

		# High bits
		for pin in self.pins_db:
			GPIO.output(pin, False)
		if bits&0x10==0x10:
			GPIO.output(self.pins_db[0], True)
		if bits&0x20==0x20:
			GPIO.output(self.pins_db[1], True)
		if bits&0x40==0x40:
			GPIO.output(self.pins_db[2], True)
		if bits&0x80==0x80:
			GPIO.output(self.pins_db[3], True)

		# Toggle 'Enable' pin
		sleep(HD44780._DELAY)    
		GPIO.output(self.pin_e, True)  
		sleep(HD44780._PULSE)
		GPIO.output(self.pin_e, False)  
		sleep(HD44780._DELAY)      

		# Low bits
		for pin in self.pins_db:
			GPIO.output(pin, False)
		if bits&0x01==0x01:
			GPIO.output(self.pins_db[0], True)
		if bits&0x02==0x02:
			GPIO.output(self.pins_db[1], True)
		if bits&0x04==0x04:
			GPIO.output(self.pins_db[2], True)
		if bits&0x08==0x08:
			GPIO.output(self.pins_db[3], True)

		# Toggle 'Enable' pin
		sleep(HD44780._DELAY)    
		GPIO.output(self.pin_e, True)  
		sleep(HD44780._PULSE)
		GPIO.output(self.pin_e, False)  
		sleep(HD44780._DELAY) 	

	######################
	#Affichage sur le LCD# 
	######################	
	def LcdMessage(self):
		""" Send string to LCD. Newline wraps to second line"""
 		text = self.currentmessage
 		self.LcdByte(0x80, False)
		lines = text.split("\n")
		line1=lines[0].ljust(self.lcd_width, " ")
		if (len(lines)>1):
			line2 = lines[1].ljust(self.lcd_width, " ")
		else:
			line2= " ".ljust(self.lcd_width, " ")
			
 		for c in line1:
 			self.LcdByte(ord(c),True)
		self.LcdByte(0xC0, False) # next line
 		for c in line2:
 			self.LcdByte(ord(c),True)

	######################
	#Definir le message  # 
	######################
	def LcdSetMessage(self, text):
		self.message = text

class UINavigation(threading.Thread):
	
	def __init__(self):    
		GPIO.setmode(GPIO.BOARD)
		GPIO.setup(11, GPIO.IN)
		GPIO.setup(15, GPIO.IN)
		A_PIN  = 7
		B_PIN  = 9
		self.encoder = gaugette.rotary_encoder.RotaryEncoder.Worker(A_PIN, B_PIN)
		self.encoder.start()
		self.current_artist=0
		self.current_artist_album_count=0
		self.current_radio=0
		self.current_album=0
		self.left=False
		self.right=False
		self.push=False
		self.back=False
		self.level="root"
		self.cursor=0
		self.sbs = SqueezeBoxServer(host="192.168.0.100",port=9000, player_id="80:1f:02:82:3a:50")
		self.lcd= HD44780()
		self.sbs.setVolume(100)
		self.paused = False
		threading.Thread.__init__(self)
		
	def affiche(self,texte):
		self.lcd.LcdSetMessage(texte)
		#print(texte)
		
	def update_screen(self):
		if (self.level == "root"):
			if (self.cursor==0):
				self.affiche('Radio')
			if (self.cursor==1):
				self.affiche('Artistes')
		elif (self.level == "artist"):
			self.affiche(self.sbs.getArtists()[self.current_artist]['artist'])
		elif (self.level == "radio"):
			if (self.paused==False):
				self.affiche(self.sbs.getCurrentRadioTitle(self.current_radio))
			else:
				self.affiche("Pause - " + self.sbs.getCurrentRadioTitle(self.current_radio))
		elif (self.level == "album"):
			self.affiche(self.sbs.getArtistAlbum(self.sbs.getArtists()[self.current_artist]['id'])[self.current_album]['album'])
		elif (self.level == "song"):
			if (self.paused==False):
				self.affiche(self.sbs.getArtists()[self.current_artist]['artist']+"\n"+self.sbs.getCurrentSongTitle())	
			else:
				self.affiche("Pause - " + self.sbs.getCurrentSongTitle())

	def lbutton(self, fast=False):  #Left BUTTON
		if (fast):
			fast_increment = 20
		else:
			fast_increment = 0
		if(self.level == "root"):
			if (self.cursor==1):
				self.cursor=0
				self.update_screen()
			elif (self.cursor==0):
				self.cursor=1
				self.update_screen()
 		elif (self.level == "artist"):
			self.current_artist-=1+fast_increment
			if (self.current_artist<0):
				self.current_artist = self.sbs.getArtistsCount()-1
			self.update_screen()
		elif (self.level == "radio"):
			if (self.current_radio>0):
				self.current_radio-=1
				self.sbs.playRadio(self.current_radio)
				self.update_screen()
		elif (self.level == "album"):
			if (self.current_album>0):
				self.current_album-=1
				self.update_screen()
		elif (self.level == "song"):
				self.sbs.previousSong()
				self.paused = False
				self.update_screen();
	
	def rbutton(self, fast=False):	#Right BUTTON	
		if (fast):
			fast_increment = 20
		else:
			fast_increment = 0
		if (self.level == "root"):
			if (self.cursor==1):
				self.cursor=0
				self.update_screen()
			elif (self.cursor==0):
				self.cursor=1
				self.update_screen()
		elif (self.level == "artist"):
			self.current_artist+=1 + fast_increment
			if (self.current_artist>=self.sbs.getArtistsCount()-1):
				self.current_artist=0
			self.update_screen()
		elif (self.level == "radio"):
			if (self.current_radio<self.sbs.getRadiosCount()-1):
				self.current_radio+=1
				self.sbs.playRadio(self.current_radio)
				self.update_screen()
		elif (self.level == "album"):
			if (self.current_album<len(self.sbs.getArtistAlbum(self.sbs.getArtists()[self.current_artist]['id']))-1):
				self.current_album+=1
				self.update_screen()
		elif (self.level == "song"):
			self.sbs.nextSong()
			self.paused = False
			self.update_screen()
	
	def pbutton(self):  #Push BUTTON
		if (self.level == "root"):
			if (self.cursor==0):
				self.level="radio"
				self.sbs.playRadio(self.current_radio)
				self.update_screen()
			if (self.cursor==1):
				self.level="artist"
				self.update_screen()
		elif (self.level == "artist"): 
			self.level="album"
			self.update_screen()
#		elif (self.level == "radio"):
#			self.sbs.playRadio(self.current_radio)
		elif (self.level == "album"):
			self.level="song"
			id=self.sbs.getArtistAlbum(self.sbs.getArtists()[self.current_artist]['id'])[self.current_album]['id']
			self.sbs.playAlbum(id)
			self.paused=False
			self.update_screen()
		elif ((self.level == "song") or (self.level == "radio")):
			self.sbs.pause()
			self.paused = not self.paused
			self.update_screen()
			
	
	def bbutton(self):  #Back BUTTON
		if (self.level == "artist"):
			self.level="root"
			self.update_screen()
		elif (self.level ==  "radio"):
			self.level="root"
			self.update_screen()
		elif (self.level == "album"):
			self.level="artist"
			self.current_album=0
			self.update_screen()
		elif (self.level == "song"):
			self.level="album"
			self.update_screen()

	def run(self):
		self.lcd.start()
		self.stop=False
		tempo=.05
		horloge=0
		cumul=0
		self.update_screen()
		while(self.stop==False):
			if (self.level=="song"):
				horloge+=1
				if (horloge>(5/tempo)): #refresh screen every 5 seconds if playing song
					self.update_screen()
					horloge=0
					
			delta = self.encoder.get_delta()
			cumul += delta	
			
			if (cumul>=4):
				cumul=0
				self.rbutton(delta>=6)
			
			if (cumul<=-4):
				cumul=0
				self.lbutton(delta<=-6)
		
			if(self.push==True):
				if(GPIO.input(11)==False):
					#print "BUTTON PUSH PRESSED"
					self.pbutton()
			self.push = GPIO.input(11)
        
			if(self.back==False):
				if(GPIO.input(15)==True):
					#print "BUTTON BACK PRESSED"
					self.bbutton()
			self.back = GPIO.input(15)
			sleep(tempo)
				
	def Stop(self):
		self.lcd.Clear()
		self.stop=True
		self.lcd.Stop()

if __name__ == '__main__':
#	lcd = HD44780()
#	lcd.start()
		ui = UINavigation()
		ui.start() 
		q = str(raw_input('Press ENTER to quit program\n'))
		ui.Stop()