#!/usr/bin/python
# -*- coding: utf-8 -*-

import subprocess
import MySQLdb
import re
import sys
import json
import os
import decimal
import ConfigParser
from variableSet import dataField
from variableSet import variableSet
from variableSet import splitMySQLcode

import warnings
warnings.filterwarnings('ignore', 'Table .* already exists')
warnings.filterwarnings("ignore", "Can't create database.*; database exists")

class DB:
    def __init__(self,dbname=None):
        config = ConfigParser.ConfigParser(allow_no_value=True)
        config.read(["~/.my.cnf","/etc/my.cnf","/etc/mysql/my.cnf","bookworm.cnf"])
        if dbname==None:
            self.dbname = config.get("client","database")
        else:
            self.dbname = dbname
        self.username=config.get("client","user")
        self.password=config.get("client","password")
        self.conn = None

    def connect(self):
        #These scripts run as the Bookworm _Administrator_ on this machine; defined by the location of this my.cnf file.
        self.conn = MySQLdb.connect(read_default_file="~/.my.cnf",use_unicode='True', charset='utf8', db='', local_infile=1)
        cursor = self.conn.cursor()
        cursor.execute("CREATE DATABASE IF NOT EXISTS %s" % self.dbname)
        #Don't use native query attribute here to avoid infinite loops
        cursor.execute("SET NAMES 'utf8'")
        cursor.execute("SET CHARACTER SET 'utf8'")
        cursor.execute("SET default_storage_engine=MYISAM")
        cursor.execute("USE %s" % self.dbname)

    def query(self, sql):
        """
        Billy defined a separate query method here so that the common case of a connection being
        timed out doesn't cause the whole shebang to fall apart: instead, it just reboots
        the connection and starts up nicely again.
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(sql)
        except:
            try:
                self.connect()
                cursor = self.conn.cursor()
                cursor.execute(sql)
            except:
                print "\n" + sql + "\n"
                raise
        return cursor

class BookwormSQLDatabase:

    """
    This class gives interactions methods to a MySQL database storing Bookworm data.
    Although the primary methods are about loading data already created
    into the SQL database, it has a few other operations
    that write out text files needed by the API and the web front end:
    I take it as logical to do those here, since that how
    it fits chronologically in the bookworm-creation sequence.
    """

    def __init__(self,dbname=None,variableFile="files/metadata/jsoncatalog_derived.txt"):
        config = ConfigParser.ConfigParser(allow_no_value=True)
        config.read(["~/.my.cnf","/etc/my.cnf","/etc/mysql/my.cnf","bookworm.cnf"])
        if dbname==None:
            self.dbname = config.get("client","database")
        else:
            self.dbname = dbname
        self.conn = None

        self.db = DB(dbname=self.dbname)
        if variableFile is not None:
            self.setVariables(originFile=variableFile)

    def grantPrivileges(self):
        #Grants select-only privileges to a non-admin mysql user for the API to
        #query with (safer).
        config = ConfigParser.ConfigParser(allow_no_value=True)
        config.read(["~/.my.cnf","/etc/my.cnf","/etc/mysql/my.cnf","bookworm.cnf"])
        username=config.get("client","user")
        password=config.get("client","password")
        self.db.query("GRANT SELECT ON %s.* TO '%s'@'localhost' IDENTIFIED BY '%s'" % (self.dbname,username,password))
        
    
    def setVariables(self,originFile,anchorField="bookid",jsonDefinition="files/metadata/field_descriptions_derived.json"):
        self.variableSet = variableSet(originFile=originFile, anchorField=anchorField, jsonDefinition=jsonDefinition,db=self.db)

    def importNewFile(self,originFile,anchorField,jsonDefinition):
        self.setVariables(originFile,anchorField=anchorField,jsonDefinition=jsonDefinition)
        self.load_book_list()
        self.variableSet.updateMasterVariableTable()
        self.reloadMemoryTables()

    def create_database(self):
        dbname = self.dbname
        dbuser = self.dbuser
        dbpassword = self.dbpassword
        db = self.db
        #This must be run as a MySQL user with create_table privileges
        try:
            db.query("CREATE DATABASE " + dbname)
        except:
            print "Database %s already exists: that might be intentional, so not dying" % dbname

        "Setting up permissions for web user..."
        db.query("GRANT SELECT ON " + dbname + ".*" + " TO '" + dbuser + "'@'localhost' IDENTIFIED BY '" + dbpassword + "'")
        db.query("FLUSH PRIVILEGES")
        try:
            #a field to store stuff we might need later.
            db.query("CREATE TABLE IF NOT EXISTS bookworm_information (entry VARCHAR(255), PRIMARY KEY (entry), value VARCHAR(50000))")
        except:
            raise

    def load_word_list(self):
        db = self.db
        print "Making a SQL table to hold the words"
        db.query("""DROP TABLE IF EXISTS words""")
        db.query("""CREATE TABLE IF NOT EXISTS words (
        wordid MEDIUMINT,
        word VARCHAR(255), INDEX (word),
        count BIGINT UNSIGNED,
        casesens VARBINARY(255),
        stem VARCHAR(255)
        );""")

        db.query("ALTER TABLE words DISABLE KEYS")
        print "loading data using LOAD DATA LOCAL INFILE"
        db.query("""LOAD DATA LOCAL INFILE 'files/texts/wordlist/wordlist.txt'
                   INTO TABLE words
                   CHARACTER SET binary
                   (wordid,word,count) """)
        print "creating indexes on words table"
        db.query("ALTER TABLE words ENABLE KEYS")
        db.query("UPDATE words SET casesens=word")

    def load_book_list(self):
        """
        Loads in the tables that have already been created by calling
        `Bookworm.variableSet.writeMetadata()`
        """
        self.variableSet.loadMetadata()

    def create_unigram_book_counts(self):
        db = self.db
        db.query("""DROP TABLE IF EXISTS master_bookcounts""")
        print "Making a SQL table to hold the unigram counts"
        db.query("""CREATE TABLE master_bookcounts (
        bookid MEDIUMINT UNSIGNED NOT NULL, INDEX(bookid,wordid,count),
        wordid MEDIUMINT UNSIGNED NOT NULL, INDEX(wordid,bookid,count),
        count MEDIUMINT UNSIGNED NOT NULL);""")
        db.query("ALTER TABLE master_bookcounts DISABLE KEYS")
        print "loading data using LOAD DATA LOCAL INFILE"
        for filename in os.listdir("files/texts/encoded/unigrams"):
            try:
                db.query("LOAD DATA LOCAL INFILE 'files/texts/encoded/unigrams/"+filename+"' INTO TABLE master_bookcounts CHARACTER SET utf8 (bookid,wordid,count);")
            except:
                raise
        print "Creating Unigram Indexes"
        db.query("ALTER TABLE master_bookcounts ENABLE KEYS")

    def create_sixgram_book_counts(self):
        db = self.db
        print "Making a SQL table to hold the sixgram counts"
        db.query("""DROP TABLE IF EXISTS master_sixgrams""")
        db.query("""CREATE TABLE master_sixgrams (
        bookid MEDIUMINT UNSIGNED NOT NULL,
        word1 MEDIUMINT UNSIGNED NOT NULL, INDEX (word1,word2,word3,word4,word5,word6,bookid,count),
        word2 MEDIUMINT UNSIGNED NOT NULL,
        word3 MEDIUMINT UNSIGNED NOT NULL,
        word4 MEDIUMINT UNSIGNED NOT NULL,
        word5 MEDIUMINT UNSIGNED NOT NULL,
        word6 MEDIUMINT UNSIGNED NOT NULL,
        count MEDIUMINT UNSIGNED NOT NULL);""")
        db.query("ALTER TABLE master_sixgrams DISABLE KEYS")
        print "loading data using LOAD DATA LOCAL INFILE"
        for filename in os.listdir("files/texts/encoded/sixgrams"):
            try:
                db.query("LOAD DATA LOCAL INFILE 'files/texts/encoded/sixgrams/"+filename+"' INTO TABLE master_sixgrams CHARACTER SET utf8 (bookid,word1,word2,word3,word4,word5,word6,count);")
            except:
                raise
        print "Creating sixgram indexes"
        db.query("ALTER TABLE master_sixgrams ENABLE KEYS")

    def create_fivegram_book_counts(self):
        db = self.db
        print "Making a SQL table to hold the fivegram counts"
        db.query("""DROP TABLE IF EXISTS master_fivegrams""")
        db.query("""CREATE TABLE master_fivegrams (
        bookid MEDIUMINT UNSIGNED NOT NULL,
        word1 MEDIUMINT UNSIGNED NOT NULL, INDEX (word1,word2,word3,word4,word5,bookid,count),
        word2 MEDIUMINT UNSIGNED NOT NULL,
        word3 MEDIUMINT UNSIGNED NOT NULL,
        word4 MEDIUMINT UNSIGNED NOT NULL,
        word5 MEDIUMINT UNSIGNED NOT NULL,
        count MEDIUMINT UNSIGNED NOT NULL);""")
        db.query("ALTER TABLE master_fivegrams DISABLE KEYS")
        print "loading data using LOAD DATA LOCAL INFILE"
        for filename in os.listdir("files/texts/encoded/fivegrams"):
            try:
                db.query("LOAD DATA LOCAL INFILE 'files/texts/encoded/fivegrams/"+filename+"' INTO TABLE master_fivegrams CHARACTER SET utf8 (bookid,word1,word2,word3,word4,word5,count);")
            except:
                raise
        print "Creating fivegram indexes"
        db.query("ALTER TABLE master_fivegrams ENABLE KEYS")

    def create_fourgram_book_counts(self):
        db = self.db
        print "Making a SQL table to hold the fourgram counts"
        db.query("""DROP TABLE IF EXISTS master_fourgrams""")
        db.query("""CREATE TABLE master_fourgrams (
        bookid MEDIUMINT UNSIGNED NOT NULL,
        word1 MEDIUMINT UNSIGNED NOT NULL, INDEX (word1,word2,word3,word4,bookid,count),
        word2 MEDIUMINT UNSIGNED NOT NULL,
        word3 MEDIUMINT UNSIGNED NOT NULL,
        word4 MEDIUMINT UNSIGNED NOT NULL,
        count MEDIUMINT UNSIGNED NOT NULL);""")
        db.query("ALTER TABLE master_fourgrams DISABLE KEYS")
        print "loading data using LOAD DATA LOCAL INFILE"
        for filename in os.listdir("files/texts/encoded/fourgrams"):
            try:
                db.query("LOAD DATA LOCAL INFILE 'files/texts/encoded/fourgrams/"+filename+"' INTO TABLE master_fourgrams CHARACTER SET utf8 (bookid,word1,word2,word3,word4,count);")
            except:
                raise
        print "Creating fourgram indexes"
        db.query("ALTER TABLE master_fourgrams ENABLE KEYS")

    def create_trigram_book_counts(self):
        db = self.db
        print "Making a SQL table to hold the trigram counts"
        db.query("""DROP TABLE IF EXISTS master_trigrams""")
        db.query("""CREATE TABLE master_trigrams (
        bookid MEDIUMINT UNSIGNED NOT NULL,
        word1 MEDIUMINT UNSIGNED NOT NULL, INDEX (word1,word2,word3,bookid,count),
        word2 MEDIUMINT UNSIGNED NOT NULL,
        word3 MEDIUMINT UNSIGNED NOT NULL,
        count MEDIUMINT UNSIGNED NOT NULL);""")
        db.query("ALTER TABLE master_trigrams DISABLE KEYS")
        print "loading data using LOAD DATA LOCAL INFILE"
        for filename in os.listdir("files/texts/encoded/trigrams"):
            try:
                db.query("LOAD DATA LOCAL INFILE 'files/texts/encoded/trigrams/"+filename+"' INTO TABLE master_trigrams CHARACTER SET utf8 (bookid,word1,word2,word3,count);")
            except:
                raise
        print "Creating trigram indexes"
        db.query("ALTER TABLE master_trigrams ENABLE KEYS")

    def create_bigram_book_counts(self):
        db = self.db
        print "Making a SQL table to hold the bigram counts"
        db.query("""DROP TABLE IF EXISTS master_bigrams""")
        db.query("""CREATE TABLE master_bigrams (
        bookid MEDIUMINT UNSIGNED NOT NULL,
        word1 MEDIUMINT UNSIGNED NOT NULL, INDEX (word1,word2,bookid,count),
        word2 MEDIUMINT UNSIGNED NOT NULL,
        count MEDIUMINT UNSIGNED NOT NULL);""")
        db.query("ALTER TABLE master_bigrams DISABLE KEYS")
        print "loading data using LOAD DATA LOCAL INFILE"
        for filename in os.listdir("files/texts/encoded/bigrams"):
            try:
                db.query("LOAD DATA LOCAL INFILE 'files/texts/encoded/bigrams/"+filename+"' INTO TABLE master_bigrams CHARACTER SET utf8 (bookid,word1,word2,count);")
            except:
                raise
        print "Creating bigram indexes"
        db.query("ALTER TABLE master_bigrams ENABLE KEYS")

    def loadVariableDescriptionsIntoDatabase(self):
        """
        This adds a description of files to the master variable table:
        also, crucially, it puts code specifying their fast creation there,
        where it will be executed on startup for all eternity.
        """
        db = self.db
        db.query("DROP TABLE IF EXISTS masterVariableTable")
        m = db.query("""
            CREATE TABLE IF NOT EXISTS masterVariableTable
              (dbname VARCHAR(255), PRIMARY KEY (dbname),
              name VARCHAR(255),
              type VARCHAR(255),
              tablename VARCHAR(255),
              anchor VARCHAR(255),
              alias VARCHAR(255),
              status VARCHAR(255),
              description VARCHAR(5000)
              ) ENGINE=MYISAM;
              """)
        tableTable = db.query("""
            CREATE TABLE IF NOT EXISTS masterTableTable
              (tablename VARCHAR(255), PRIMARY KEY (tablename),
              dependsOn VARCHAR(255),
              memoryCode VARCHAR(20000)) ENGINE=MYISAM;
              """)
        self.addFilesToMasterVariableTable()
        self.addWordsToMasterVariableTable()
        self.variableSet.updateMasterVariableTable()

    def reloadMemoryTables(self):
        existingCreateCodes = self.db.query("SELECT tablename,memoryCode FROM masterTableTable").fetchall();
        for row in existingCreateCodes:
            """
            For each table, it checks to see if the table is currently populated; if not,
            it runs the stored code to repopulate the table. (It checks length because
            memory tables are emptied on a restart).
            """
            tablename = row[0]
            try:
                cursor = self.db.query("SELECT count(*) FROM %s" %(tablename))
                currentLength = cursor.fetchall()[0][0]
            except:
                currentLength = 0
            if currentLength==0:
                for query in splitMySQLcode(row[1]):
                    self.db.query(query)

    def addFilesToMasterVariableTable(self):
        fileCommand = """DROP TABLE IF EXISTS tmp;
        CREATE TABLE tmp
        (bookid MEDIUMINT, PRIMARY KEY (bookid),
        nwords MEDIUMINT,""" +",\n".join([variable.fastSQL() for variable in self.variableSet.variables if (variable.unique and variable.fastSQL() is not None)]) + """
        ) ENGINE=MEMORY;"""
        #Also update the wordcounts for each text.
        fileCommand += "INSERT INTO tmp SELECT bookid,nwords, " + ",".join([variable.fastField for variable in self.variableSet.variables if variable.unique and variable.fastSQL() is not None]) + " FROM catalog " + " ".join([" JOIN %(field)s__id USING (%(field)s ) " % variable.__dict__ for variable in self.variableSet.variables if variable.unique and variable.fastSQL() is not None and variable.datatype=="categorical"])+ ";"
        fileCommand += "DROP TABLE IF EXISTS fastcat;"
        fileCommand += "RENAME TABLE tmp TO fastcat;"
        self.db.query("""INSERT IGNORE INTO masterTableTable VALUES
                   ('fastcat','fastcat','""" + fileCommand + """')""")

    def addWordsToMasterVariableTable(self):
        wordCommand = "DROP TABLE IF EXISTS tmp;"
        wordCommand += "CREATE TABLE tmp (wordid MEDIUMINT, PRIMARY KEY (wordid), word VARCHAR(30), INDEX (word), casesens VARBINARY(30),UNIQUE INDEX(casesens), lowercase CHAR(30), INDEX (lowercase) ) ENGINE=MEMORY;"
        wordCommand += "INSERT IGNORE INTO tmp SELECT wordid as wordid,word,casesens,LOWER(word) FROM words WHERE CHAR_LENGTH(word) <= 30 AND wordid <= 1500000 ORDER BY wordid;"
        wordCommand += "DROP TABLE IF EXISTS wordsheap;"
        wordCommand += "RENAME TABLE tmp TO wordsheap;"
        query = """INSERT IGNORE INTO masterTableTable
                   VALUES ('wordsheap','wordsheap','""" + MySQLdb.escape_string(wordCommand) + """')"""
        self.db.query(query)
        
    def jsonify_data(self):
        variables = self.variableSet.variables
        dbname = self.dbname
        #This creates a JSON file compliant with the Bookworm web site.
        #Deprecated.
        output = dict()
        output['settings'] = {
                              "dbname": self.dbname,
                              "itemName":" text",
                              "sourceName": self.dbname,
                              "sourceURL": self.dbname
                             }
        ui_components = [
                         {
                          "type":"text",
                          "dbfield":"word",
                          "name":"Word(s)"
                         }
                        ]
        for variable in variables:
            newdict = variable.jsonDict()
            if newdict: #(It can be empty, in which case we don't want it for the json)
                ui_components.append(newdict)
        try:
            mytime = [variable.field for variable in variables if variable.datatype=='time'][0]
            output['default_search']  = [
                                         {
                                          "search_limits": [{"word":["test"]}],
                                          "time_measure": mytime,
                                          "words_collation": "Case_Sensitive",
                                          "counttype": "Occurrences_per_Million_Words",
                                          "smoothingSpan": 0
                                         }
                                        ]
        except:
            print "WARNING: Not enough info for a default search (like, no time variable maybe?)--likely to be some big problems with your bookworm."
        output['ui_components'] = ui_components
        outfile = open('files/%s.json' % dbname, 'w')
        outfile.write(json.dumps(output))

    def create_API_settings(self):
        db = self.db
        try:
            db.query("DROP TABLE IF EXISTS API_settings")
            db.query("CREATE TABLE API_settings (settings VARCHAR(8192));")
        except:
            pass
        api_info = {
                    "HOST": "10.102.15.45",
                    "database": self.dbname,
                    "read_default_file": "/etc/mysql/my.cnf",
                   }
        addCode = json.dumps(api_info)
        print addCode
        db.query("INSERT INTO API_settings VALUES ('%s');" % addCode)

    def update_Porter_stemming(self): #We use stems occasionally.
        print "Updating stems from Porter algorithm..."
        from nltk import PorterStemmer
        stemmer = PorterStemmer()
        cursor = db.query("""SELECT word FROM words""")
        words = cursor.fetchall()
        for local in words:
            word = ''.join(local) #Could probably take the first element of the tuple as well?
            #Apostrophes have the save stem as the word, if they're included
            word = word.replace("'s","")
            if re.match("^[A-Za-z]+$",word):
                query = """UPDATE words SET stem='""" + stemmer.stem(''.join(local)) + """' WHERE word='""" + ''.join(local) + """';"""
                z = cursor.execute(query)

    def addCategoricalFromFile(self,filename,unique=False):
        """
        Useful, but still a bit of a hack--should be a special method of adding a group
        that automatically creates the json file.
        """
        file = open(filename)
        firstTwo = file.readline().split("\t")
        name = firstTwo[1].rstrip("\n")
        anchor = firstTwo[0]
        definition = {"field":name,"datatype":"categorical","type":"character","unique":False}

        #Currently the anchortype has to be a MediumInt.
        #That's extremely inefficient.
        anchorType = "MEDIUMINT"

        thisField = dataField(definition,
                              self.db,
                              anchorType,
                              anchor=firstTwo[0],
                              table=definition["field"]+"Disk",
                              fasttab=definition["field"] + "Heap")

        thisField.buildDiskTable(fileLocation=filename)

        thisField.buildLookupTable()

        self.db.query(thisField.updateVariableDescriptionTable())

        query = "SELECT memoryCode FROM masterVariableTable WHERE name='%s'" % (name)
        print query;
        commands = self.db.query(query).fetchall()[0][0];
        for query in splitMySQLcode(commands):
            self.db.query(query)
