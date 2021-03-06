#!/usr/bin/env python

import MySQLdb
import re
import sys
import json
import os
import ConfigParser
from subprocess import call

# These four libraries define the Bookworm-specific methods.
from bookworm.MetaParser import *
from bookworm.CreateDatabase import *

# Pull a method from command line input.
try:
    methods = [sys.argv[1]]

except IndexError:
    print """Give as a command argument one of the following:
    metadata
    wordcounts
    database
    """
    methods = []
    #methods = ["metadata","wordcounts","database"]

#Use the client listed in the my.cnf file for access

config = ConfigParser.ConfigParser(allow_no_value=True)
config.read(["bookworm.cnf"])
dbname = config.get("client","database")
dbuser = config.get("client","user")
dbpassword = config.get("client","password")


# Initiate MySQL connection.
class oneClickInstance(object):
    #The instance has methods corresponding to what you want to make:
    #they should be passed in, in the order you want them
    #to be run.

    def __init__(self):
        pass

    def diskMetadata(self):
        print "Parsing field_descriptions.json"
        ParseFieldDescs()
        print "Parsing jsoncatalog.txt"
        ParseJSONCatalog()
        
    def preDatabaseMetadata(self):
        Bookworm = BookwormSQLDatabase()
        print "Writing metadata to new catalog file..."        
        Bookworm.variableSet.writeMetadata()

        # This creates helper files in the /metadata/ folder.

    def metadata(self):
        self.diskMetadata()
        self.preDatabaseMetadata()


    def guessAtFieldDescriptions(self):
        Bookworm = BookwormSQLDatabase(dbname,variableFile=None)
        Bookworm.setVariables("files/metadata/jsoncatalog.txt",jsonDefinition=None)
        import os
        if not os.path.exists("files/metadata/field_descriptions.json"):
            output = open("files/metadata/field_descriptions.json","w")
            output.write(json.dumps(Bookworm.variableSet.guessAtFieldDescriptions()))
            
    def reloadMemory(self):
        Bookworm = BookwormSQLDatabase(dbname,variableFile=None)
        Bookworm.reloadMemoryTables()

    def reloadAllMemory(self):
        #reloads the memory tables for every bookworm on the server.
        datahandler = BookwormSQLDatabase('tmp',variableFile=None)
        cursor = datahandler.db.query("SELECT TABLE_SCHEMA FROM information_schema.tables WHERE TABLE_NAME='masterTableTable'")
        for row in cursor.fetchall():
            Bookworm = BookwormSQLDatabase(row[0],variableFile=None)
            Bookworm.reloadMemoryTables()

    def database_metadata(self):
        Bookworm = BookwormSQLDatabase(dbname)
        Bookworm.load_book_list()

        # This creates a table in the database that makes the results of
        # field_descriptions accessible through the API, and updates the
        Bookworm.loadVariableDescriptionsIntoDatabase()

        # This needs to be run if the database resets. It builds a
        # temporary MySQL table and the GUI will not work if this table is not built.
        Bookworm.reloadMemoryTables()

        print "adding cron job to automatically reload memory tables on launch"
        print "(this assumes this machine is the MySQL server, which need not be the case)"

        subprocess.call(["sh","scripts/scheduleCronJob.sh"])

        Bookworm.jsonify_data() # Create the dbname.json file in the root directory.
        Bookworm.create_API_settings()

        Bookworm.grantPrivileges()

    def supplementMetadataFromTSV(self):
        """
        A lightweight way to add metadata linked to elements.
        Reads a categorical variable from a .tsv file.
        First column is an existing anchor:
        Second column is the new data that's being inserted.
        That file MUST have as its first row.
        """

        from bookworm.convertTSVtoJSONarray import convertToJSON
        Bookworm = BookwormSQLDatabase()
        filename = sys.argv.pop()
        #The anchor MUST be the first column
        anchor = open(filename).readline().split("\t")[0]
        print ("anchoring to " + anchor)
        #this writes it to a new table called "tmp.txt"
        convertToJSON(filename)
        #Should this be specifiable here? Well, it isn't...
        fieldDescriptions = None
        Bookworm.importNewFile("tmp.txt",anchorField=anchor,jsonDefinition=fieldDescriptions)


    def supplementMetadataFromJSON(self):
        """
        This is a more powerful method to import a json dictionary of the same form
        as jsoncatalog.txt. (More powerful because it lets you use a combination of
        files, arrays instead of single elements, and a specification for each element.)
        """

        if len(sys.argv) > 4:
            #If there are multiple entries for each element, you can specify 'unique'
            # by typing "False" as the last entry.
            field_descriptions = sys.argv.pop()
        else:
            field_descriptions = None
            print "guessing at field descriptions for the import"
        """
        The anchor should be intuited, not named.
        """
        anchor = sys.argv.pop()

        if len(sys.argv)==3:
            filename = sys.argv.pop()
        else:
            print "you must supply exactly one argument to 'addCategoricalFromFile'"
            raise
        Bookworm=BookwormSQLDatabase()
        Bookworm.importNewFile(filename,anchorField=anchor,jsonDefinition=field_descriptions)


    def database_wordcounts(self):
        """
        Builds the wordcount components of the database. This will die
        if you can't connect to the database server.
        """
        Bookworm = BookwormSQLDatabase()
        Bookworm.load_word_list()
        Bookworm.create_unigram_book_counts()
        Bookworm.create_bigram_book_counts()
        Bookworm.create_trigram_book_counts()
        Bookworm.create_fourgram_book_counts()
        Bookworm.create_fivegram_book_counts()
        Bookworm.create_sixgram_book_counts()

    def database(self):
        self.database_wordcounts()
        self.database_metadata()


if __name__=="__main__":
    program = oneClickInstance()
    for method in methods:
        getattr(program,method)()
