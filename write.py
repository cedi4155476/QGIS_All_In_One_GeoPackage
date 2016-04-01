# coding=latin-1

from qgis.core import *
from PyQt4.QtCore import *
import tempfile
import os
import sqlite3
from xml.etree import ElementTree as ET


class Write():
    def __init__(self, iface, parent=None):
        ''' Klasse wird initialisiert '''
        self.parent = parent
        self.iface = iface

    def read_project(self, path):
        ''' Überprüfen ob es sich um ein File handelt und dieses dann als ElementTree objekt zurückgeben '''
        if not os.path.isfile(path):
            return

        return ET.parse(path)

    def database_connect(self, path):
        ''' Datenbank mit sqlite3 Verbinden, bei Fehlschlag wird False zurückgegeben '''
        try:
            self.conn = sqlite3.connect(path)
            self.c = self.conn.cursor()
            return True
        except:
            return False

    def check_gpkg(self, path):
        ''' Es wird überprüft, ob die Datei wirklich ein Geopackage ist '''
        # TODO: ist das möglich?
        return True
        # sql = u"SELECT CheckGeoPackageMetaData()"
        # result = self.c.execute(sql).fetchone()[0] == 1
        # return result

    def make_path_absolute(self, path, project_path):
        ''' Pfad wird Absolut und Betriebsystemübergreifend gemacht'''
        if not os.path.isabs(path):
            path = os.path.join(os.path.dirname(project_path), path)
        return os.path.normpath(path)

    def run(self):
        ''' Hauptfunktion in welcher alles Abläuft '''
        project = QgsProject.instance()
        if project.isDirty():
            # Wenn das Projekt seit dem letzten bearbeiten nicht gespeichert wurde,
            # wird eine Temporärdatei erstellt und dann gelöscht
            tmpfile = os.path.join(tempfile.gettempdir(), "temp_project.qgs")
            file_info = QFileInfo(tmpfile)
            project.write(file_info)
            project_path = project.fileName()
            xmltree = self.read_project(project_path)
            os.remove(project.fileName())
            project.dirty(True)
        else:
            # Sonst wird einfach der Pfad die Datei selber verwendet
            project_path = project.fileName()
            xmltree = self.read_project(project_path)
            project.dirty(False)

        root = xmltree.getroot()
        projectlayers = root.find("projectlayers")

        # Es wird nach allen Daten-quellen gesucht
        sources = []
        for layer in projectlayers:
            layer_path = self.make_path_absolute(layer.find("datasource").text.split("|")[0], project_path)
            if layer_path not in sources:
                sources.append(layer_path)

        # Sind mehrere Datenquellen vorhanden müssen deren Ursprung überprüft werden
        if len(sources) > 1:
            gpkg_found = False
            for path in sources:
                if self.database_connect(path):
                    if self.check_gpkg(path) and not gpkg_found:
                        gpkg_found = True
                        gpkg_path = path
                    elif self.check_gpkg(path) and gpkg_found:
                        # Hat ein Projekt Layer aus verschiedenen GeoPackage Datenbanken,
                        # kann das Einschreiben nicht ausgeführt werden
                        raise
        else:
            gpkg_path = sources[0]

        self.database_connect(gpkg_path)

        if not self.check_gpkg(gpkg_path):
            # Stammen die Layer nicht aus einer GeoPackage Datei, kann nicht weiterverarbeitet werden
            raise

        # Die Daten werden in die Datenbank eingeschrieben
        inserts = (os.path.basename(project.fileName()), ET.tostring(root))
        extensions = (None, None, 'all_in_one_geopackage', 'Insert and read a QGIS Project file into the GeoPackage database.', 'read-write')

        try:
            # Falls bereits ein Projekt vorhanden ist, wird nichts geändert
            self.c.execute('SELECT name FROM _qgis')
        except sqlite3.OperationalError:
            self.c.execute('CREATE TABLE _qgis (name text, xml text)')
            self.c.execute('INSERT INTO _qgis VALUES (?,?)', inserts)
            self.c.execute('INSERT INTO gpkg_extensions VALUES (?,?,?,?,?)', extensions)
            self.conn.commit()
