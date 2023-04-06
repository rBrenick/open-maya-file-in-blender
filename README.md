# Open Maya File In Blender

This was mostly written as a thought experiment.

<code>"What if you could directly parse an .ma file to import it into Blender"</code>

Over the years I've said many time, <i>"If there exists a file format, someone has written an importer for blender"</i>. 

As I've spent many years in Maya, I figured I'd take a stab at it.

So I found [this repo](https://github.com/mottosso/maya-scenefile-parser), and I spent a weekend modifying it and writing an implementation for geometry/uv data for Blender.

<h1>NOTE</h1>
Would not recommend using this for anything important. Opening the file in Maya and exporting an .fbx will result in 1000x more information being preserved.

<h2>How to install</h2>

Grab [a zip file from the releases](https://github.com/rBrenick/open-maya-file-in-blender/releases/download/0.00.01/open_maya_file_in_blender_0-00-01.zip), and install it as an Addon in Blender preferences. 

<h2>Where to find it</h2>

![header image](docs/header_image.png)


