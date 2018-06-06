../phmark2server.tgz: mark2server.png mark2server_dark.png readme.html \
	mark2server_connector.py mark2server.json
	phenv python2.7 /opt/phantom/bin/compile_app.pyc -i

mark2server.png: Soliton_logo.png
	convert $< -bordercolor none -border 10 $@

mark2server_dark.png: Soliton_logo_wht.png
	convert $< -bordercolor none -border 10 $@

.PHONY: clean
clean:
	rm -f *.pyc mark2server.png mark2server_dark.png
