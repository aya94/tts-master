import os
from gensim import corpora, models, similarities
import nltk.corpus as sw_corpus
import nltk.stem.porter as porter

STEMMER = porter.PorterStemmer()

from xml.dom.minidom import parseString

class Sentence():
    
    def __init__(self, sentence, valence=None, primary_emotion=None, mood=None):
        self.sentence = sentence
        self.valence = valence
        self.primary_emotion = primary_emotion
        self.mood = mood
        

class FairytaleCorpus():
    
    def __init__(self, data_folder):
        dict_data = {}
        start_idx = 0
        for data_file in os.listdir(data_folder):
            results_dict, end_idx = self.parse_fairytale_data(os.path.join(data_folder, data_file), start_idx)
            dict_data.update(results_dict)
            start_idx += end_idx
        self.sentence_data = dict_data
        self.storage_file = 'corpus_%s.mm'%(id(self),)
        data = [[self.preprocess_word(word) for word in entry.sentence.lower().split()] for entry in self.sentence_data.values()]
        dictionary = corpora.Dictionary(data)
        stop_ids = [dictionary.token2id[stopword] for stopword in sw_corpus.stopwords.words('english')
                                                            if stopword in dictionary.token2id]
        once_ids = [tokenid for tokenid, docfreq in dictionary.dfs.iteritems() if docfreq == 1]
        dictionary.filter_tokens(stop_ids + once_ids) # remove stop words and words that appear only once
        dictionary.compactify()
        self.dictionary = dictionary
    
    def parse_fairytale_data(self, file_name, start_idx=0):
        results_dict = {}
        for line in open(file_name):
            sent_id, sentence = self.process_line(line)
            results_dict[str(int(sent_id)+start_idx)] = sentence
        return results_dict, int(sent_id) + start_idx
    
    def process_line(self, line):
        first_index = line.index(':')
        sent_id = line[:first_index]
        second_index = first_index + line[first_index+1:].index(':') + 1
        primary_emo = line[first_index:second_index].split('\t')[-1]
        third_index = second_index + line[second_index+1:].index(':') + 1
        mood = line[second_index:third_index].split('\\t')[-1]
        sentence = line[third_index+1:].split('\t')[1]
        return sent_id, Sentence(sentence, primary_emotion=primary_emo, mood=mood)
            
    def __del__(self):
        if os.path.exists(self.storage_file):
            self.clear()
        
    def preprocess_word(self, word):
        return STEMMER.stem(word.replace(',', '').replace('"', '').replace("'", ''))
    
    def sentence_for_id(self, sent_id):
        return self.sentence_data.get(sent_id, None).sentence
    
    def vector_for_id(self, sent_id):
        sent = self.sentence_data.get(sent_id, None)
        if sent is None:
            # TODO: Add entry here with unknown valence ??
            raise Exception("No sentence stored so far!")
        return self.dictionary.doc2bow(sent.sentence.lower().split())
    
    def clear(self):
        if os.path.exists(self.storage_file):
            os.remove(self.storage_file)
        if os.path.exists(self.storage_file + '.index'):
            os.remove(self.storage_file + '.index')
    
    def serialize(self):
        corpora.MmCorpus.serialize(self.storage_file, self)
        
    def __iter__(self):
        for line in self.sentence_data.values():
            yield self.dictionary.doc2bow(line.sentence.lower().split())
            
    def to_sparse_arff(self, output_file, corpus_type='tfidf'):
        if corpus_type == 'tfidf':
            tfidf = models.TfidfModel(self.mm_corpus())
            words = []
            for word in self.dictionary.token2id:
                words.append((word, self.dictionary.token2id[word]))
            # Sort the words after the index so we can write our arff file.
            words = sorted(words, key=lambda x: x[1])
            print "Corpus has %i words"%(len(words))
            with open(output_file, 'w') as fp:
                fp.write('@relation tfidf_features\n\n')
                for word in words:
                    fp.write("@attribute %s numeric\n"%(word[0]))
                fp.write("@attribute primary_emotion {A,D,F,H,N,Sa,Su+,Su-}\n\n")
                fp.write("@data\n")
                for sent_id in self.sentence_data:
                    sparse_vector_rep = tfidf[self.vector_for_id(sent_id)]
                    if sparse_vector_rep:
                        data_string = '{'
                        for entry in sparse_vector_rep:
                            data_string += '%s %s,'%(entry[0], entry[1])
                        data_string += '%s %s}\n'%(len(words), self.sentence_data[sent_id].primary_emotion)
                        fp.write(data_string)
                    
            
    def mm_corpus(self):
        if not os.path.exists(self.storage_file):
            self.serialize()
        return corpora.MmCorpus(self.storage_file)
            

class SemevalCorpus():
    
    def __init__(self, data_file, valence_file):
        self.sentence_data = self.parse_semeval_data(data_file, valence_file)
        self.storage_file = 'corpus_%s.mm'%(id(self),)
        data = [[self.preprocess_word(word) for word in entry.sentence.lower().split()] for entry in self.sentence_data.values()]
        dictionary = corpora.Dictionary(data)
        stop_ids = [dictionary.token2id[stopword] for stopword in sw_corpus.stopwords.words('english')
                                                            if stopword in dictionary.token2id]
        once_ids = [tokenid for tokenid, docfreq in dictionary.dfs.iteritems() if docfreq == 1]
        dictionary.filter_tokens(stop_ids + once_ids) # remove stop words and words that appear only once
        dictionary.compactify()
        self.dictionary = dictionary
        
    def __del__(self):
        if os.path.exists(self.storage_file):
            self.clear()
        
    def preprocess_word(self, word):
        return STEMMER.stem(word.replace(',', '').replace('"', '').replace("'", ''))
        
    def parse_semeval_data(self, xml_file, valence_file):
        results_dict = {}
        data_string = open(xml_file, 'r').read()
        dom = parseString(data_string)
        instances = dom.getElementsByTagName('instance')
        for instance in instances:
            results_dict[instance.attributes['id'].nodeValue] = {'value' : instance.firstChild.nodeValue}
        for line in open(valence_file):
            sent_id, valence = line.split()
            results_dict[sent_id]['valence'] = valence
        for key in results_dict:
            results_dict[key] = Sentence(results_dict[key]['value'], results_dict[key]['valence'])
        return results_dict
        
    def sentence_for_id(self, sent_id):
        return self.sentence_data.get(sent_id, None).sentence
    
    def vector_for_id(self, sent_id):
        sent = self.sentence_data.get(sent_id, None)
        if sent is None:
            # TODO: Add entry here with unknown valence ??
            raise Exception("No sentence stored so far!")
        return self.dictionary.doc2bow(sent.sentence.lower().split())
    
    def clear(self):
        if os.path.exists(self.storage_file):
            os.remove(self.storage_file)
        if os.path.exists(self.storage_file + '.index'):
            os.remove(self.storage_file + '.index')
    
    def serialize(self):
        corpora.MmCorpus.serialize(self.storage_file, self)
        
    def __iter__(self):
        for line in self.sentence_data.values():
            yield self.dictionary.doc2bow(line.sentence.lower().split())
            
    def to_sparse_arff(self, output_file, corpus_type='tfidf', valence_class=None):
        if corpus_type == 'tfidf':
            tfidf = models.TfidfModel(self.mm_corpus())
            words = []
            for word in self.dictionary.token2id:
                words.append((word, self.dictionary.token2id[word]))
            # Sort the words after the index so we can write our arff file.
            words = sorted(words, key=lambda x: x[1])
            print "Corpus has %i words"%(len(words))
            with open(output_file, 'w') as fp:
                fp.write('@relation tfidf_features\n\n')
                for word in words:
                    fp.write("@attribute %s numeric\n"%(word[0]))
                if valence_class is None:
                    fp.write("@attribute valence numeric\n\n")
                else:
                    fp.write("@attribute valence {-1,0,1}\n\n")
                fp.write("@data\n")
                for sent_id in self.sentence_data:
                    sparse_vector_rep = tfidf[self.vector_for_id(sent_id)]
                    if sparse_vector_rep:
                        data_string = '{'
                        for entry in sparse_vector_rep:
                            data_string += '%s %s,'%(entry[0], entry[1])
                        if valence_class is None:
                            data_string += '%s %s}\n'%(len(words), self.sentence_data[sent_id].valence)
                        else:
                            valence = 0
                            if int(self.sentence_data[sent_id].valence) > 0:
                                valence = 1
                            if int(self.sentence_data[sent_id].valence) < 0:
                                valence = -1
                            data_string += '%s %s}\n'%(len(words), valence)
                        fp.write(data_string)
                    
            
    def mm_corpus(self):
        if not os.path.exists(self.storage_file):
            self.serialize()
        return corpora.MmCorpus(self.storage_file)


#corpus_memory_friendly = SemevalCorpus('affectivetext_trial.xml', 'affectivetext_trial.valence.gold')
#corpus_memory_friendly.to_sparse_arff('sample-binary.arff', valence_class='b')
grimm_data_folder = os.sep.join(['..', 'fairytales', 'Grimms', 'emmood'])
fairy_corpus = FairytaleCorpus(grimm_data_folder)
fairy_corpus.to_sparse_arff('fairytale.arff')


