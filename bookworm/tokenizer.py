#! /usr/bin/python

import regex as re
import random
import sys
import os 

def wordRegex():
    """
    #I'm including the code to create the regex, which makes it more readable.
    Note that this uses *unicode*: among other things, that means that it needs to be passed
    a unicode-decoded string: and that we have to use the "regex" module instead of the "re" module. 
    Python3 will make this, perhaps, easier.
    (See how it says import regex as re up there? Yikes.)
    """
    fp = os.path.realpath(__file__)
    fp = os.path.dirname(fp)
    fp = os.path.dirname(fp)
    cnf = os.path.join(fp, 'bookworm.cnf')

    with open(cnf) as ff:
	for line in ff:
	    if 'database' in line:
		bwname = line.split('database = ')[-1]	

    if '_phonemes' in bwname:
	print('Tokenizing text using the PHONEME regex')
	bigregex = re.compile(r'\b\w*[^\s]', re.UNICODE|re.IGNORECASE)
    else:
	print('Tokenizing text using the WORD regex')
        MasterExpression = ur"\p{L}+"
        possessive = MasterExpression + ur"'s"
        numbers = r"(?:[\$])?\d+"
        decimals = numbers + r"\.\d+"
        abbreviation = r"(?:mr|ms|mrs|dr|prof|rev|rep|sen|st|sr|jr|ft|gen|adm|lt|col|etc)\."
        sharps = r"[a-gjxA-GJX]#"
        punctuators = r"[^\p{L}\p{Z}]"
        """
        Note: this compiles looking for the most complicated words first, and as it goes on finds simpler and simpler forms 
        """
        bigregex = re.compile("|".join([decimals,possessive,numbers,abbreviation,sharps,punctuators,MasterExpression]),re.UNICODE|re.IGNORECASE)
    return bigregex

bigregex = wordRegex()

def readDictionaryFile(prefix=""):
    look = dict()
    for line in open(prefix + "files/texts/wordlist/wordlist.txt"):
        line = line.rstrip("\n")
        splat = line.split("\t")
        look[splat[1]] = splat[0]
    return look

def readIDfile(prefix=""):
    files = os.listdir(prefix + "files/texts/textids/")
    look = dict()
    for filename in files:
        for line in open(prefix + "files/texts/textids/" + filename):
            line = line.rstrip("\n")
            splat = line.split("\t")
            look[splat[1]] = splat[0]
    return look

class tokenBatches(object):
    """
    A tokenBatches is a manager for tokenizers. Each one corresponds to 
    a reasonable number of texts to read in to memory on a single processor:
    during the initial loads, there will probably be one per core. It doesn't store the original text, just the unigram and bigram tokenizations from the pickled object in its attached self.counts arrays.
    
    It writes out its data using cPickle to a single file: in this way, a batch of several hundred thousand individual files is grouped into a single file.
    It also has a method that encodes and writes its wordcounts into a tsv file appropriate for reading with mysql, with 3-byte integer encoding for wordid and bookid.

    The pickle writeout happens in between so that there's a chance to build up a vocabular using the tokenBatches.unigramCounts method. If the vocabulary were preset, it could proceed straight to writing out the encoded results.

    The pickle might be slower than simply using a fast csv module: this should eventually be investigated. But it's nice for the pickled version to just keep all the original methods.
    """
    
    def __init__(self,levels=["unigrams","bigrams", "trigrams", "fourgrams", "fivegrams", "sixgrams"]):
        self.counts = dict()
        for level in levels:
            self.counts[level] = dict()
        self.id = '%030x' % random.randrange(16**30)
        self.levels=levels

    def addFile(self,filename):
        tokens = tokenizer(open(filename).read())
        #Add trigrams to this list to do trigrams
        print tokens.string
        for ngrams in self.levels:
            self.counts[ngrams][filename] = tokens.counts(ngrams)

    def addRow(self,row):
        #row is a piece of text: the first line is the identifier, and the rest is the text.
        parts = row.split("\t",1)
        filename = parts[0]
        try:
            tokens = tokenizer(parts[1])
            for ngrams in self.levels:
                self.counts[ngrams][filename] = tokens.counts(ngrams)
        except IndexError:
            print "\nFound no tab in the input for '" + filename + "'...skipping row\n"


    def encode(self,level,IDfile,dictionary):
        #dictionaryFile is
        outputFile = open("files/texts/encoded/" + level + "/" + self.id + ".txt","w")
        output = []
        print "encoding " + level + " for " + self.id
        for key,value in self.counts[level].iteritems():
            try:
                textid = IDfile[key]
            except KeyError:
                sys.stderr.write("Warning: file " + key + " not found in jsoncatalog.txt\n")
                continue
            for wordset,count in value.iteritems():
                skip = False
                wordList = []
                for word in wordset:
                    try:
                        wordList.append(dictionary[word])
                    except KeyError:
                        """
                        if any of the words to be included is not in the dictionary,
                        we don't include the whole n-gram in the counts.
                        """
                        if level=="unigrams":
                            try:
                                sys.stderr.write(word.encode("utf-8") + u"not in dictionary, skipping\n")
                            except UnicodeDecodeError:
                                pass
                        skip = True
                if not skip:
                    wordids = "\t".join(wordList)
                    output.append("\t".join([textid,wordids,str(count)]))
                
        outputFile.write("\n".join(output))        

class tokenizer(object):
    """
    A tokenizer is initialized with a single text string.

    It assumes that you have in namespace an object called "bigregex" which
    identifies words.

    (I'd define it here, but it's a performance optimization to avoid compiling the large regex millions of times.)

    the general way to call it is to initialize, and then for each desired set of counts call "tokenizer.counts("bigrams")" (or whatever).

    That returns a dictionary, whose keys are tuples of length 1 for unigrams, 2 for bigrams, etc., and whose values are counts for that ngram. The tuple form should allow faster parsing down the road.
    
    """
    
    def __init__(self,string):
        try:
            self.string=string.decode("utf-8")
        except UnicodeDecodeError:
            print "WARNING: string can't be decoded as unicode skipping and moving on"
            print "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
            print string
            print "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
            self.string="BADDATA"

    def tokenize(self):
        """
        This tries to return the pre-made tokenization:
        if that doesn't exist, it creates it.
        """
        try:
            return self.tokens
        except:
            #return bigregex
            self.tokens = re.findall(bigregex,self.string)
            return self.tokens

    def bigrams(self):
        self.tokenize()
        return zip(self.tokens,self.tokens[1:])

    def sixgrams(self):
        self.tokenize()
        return zip(self.tokens,self.tokens[1:],self.tokens[2:], self.tokens[3:], self.tokens[4:], self.tokens[5:])

    def fivegrams(self):
        self.tokenize()
        return zip(self.tokens,self.tokens[1:],self.tokens[2:], self.tokens[3:], self.tokens[4:])

    def fourgrams(self):
        self.tokenize()
        return zip(self.tokens,self.tokens[1:],self.tokens[2:], self.tokens[3:])

    def trigrams(self):
        self.tokenize()
        return zip(self.tokens,self.tokens[1:],self.tokens[2:])

    def unigrams(self):
        self.tokenize()
        #Note the comma to enforce tupleness
        return [(x,) for x in self.tokens]
    
    def counts(self,whichType):
        count = dict()
        for gram in getattr(self,whichType)():
            try:
                count[gram] += 1
            except KeyError:
                count[gram] = 1
        return count

def getAlreadySeenList(folder):
    #Load in a list of what's already been translated for that level.
    #Returns a set.
    files = os.listdir(folder)
    seen = set([])
    for file in files:
        for line in open(folder+"/" + file):
            seen.add(line.rstrip("\n"))
    return seen

def encodeTextStream():
    IDfile = readIDfile()
    dictionary = readDictionaryFile()
    seen = getAlreadySeenList("files/texts/encoded/completed")
    tokenBatch = tokenBatches()
    written = open("files/texts/encoded/completed/" + tokenBatch.id,"w")

    for line in sys.stdin:
        filename = line.split("\t",1)[0]
        line = line.rstrip("\n")
        if filename not in seen:
            tokenBatch.addRow(line)
        if len(tokenBatch.counts['unigrams']) > 10000:
            """
            Every 10000 documents, write to disk.
            """
            for level in tokenBatch.levels:
                tokenBatch.encode(level,IDfile,dictionary)
            for file in tokenBatch.counts['unigrams'].keys():
                written.write(file + "\n")
            written.close()
            tokenBatch = tokenBatches()
            written = open("files/texts/encoded/completed/" + tokenBatch.id,"w")
            
    #And printout again at the end
    for level in tokenBatch.levels:
        tokenBatch.encode(level,IDfile,dictionary)
    for file in tokenBatch.counts['unigrams'].keys():
        written.write(file + "\n")
    written.close()
    tokenBatch = tokenBatches()
    written = open("files/texts/encoded/completed/" + tokenBatch.id,"w")

if __name__=="__main__":
    encodeTextStream()
