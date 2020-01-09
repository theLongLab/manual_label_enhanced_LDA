from wordcloud import WordCloud, STOPWORDS, ImageColorGenerator
import matplotlib.pyplot as plt
import numpy as np
import os
from collections import defaultdict
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.feature_extraction.text import TfidfVectorizer
import scipy
from sklearn import preprocessing
from scipy.sparse import vstack
from wordcloud import WordCloud, STOPWORDS, ImageColorGenerator
import matplotlib.pyplot as plt

# reverse a dictionary, let the key become value and value become key
def reverse_dict(dict_src): 
    dict_inversed = {}
    for key in dict_src.keys():
        dict_inversed[dict_src[key]] = key
    return dict_inversed

# return the list of custom stop words 
def stop_word():
    import spacy.lang.en
    import copy
    spacy_sw = spacy.lang.en.stop_words.STOP_WORDS
    sw = copy.deepcopy(spacy_sw)
    '''
    empirical_sw = ['patient','concern','complainant','state','states','concerned','pron','daughter','alberta',\
                    'edmonton','pt','states','member','family','spouse','mother','like','son','father','speak','ask','need',\
                   'brother','boyfriend','stated','wife','want','tell','say','feel','know','ll', 've']
    '''
    empirical_sw = ['patient','concern','complainant','state','concerned','pron','daughter','alberta',\
                'edmonton','husband','dr','calgary','wife','pt','states','son','mother','mom','daughter','father',\
               'dad','2010','2011','2012','2013','2014','2015','2016','2017','2018','sister','member','family','spouse','00',\
               'brother','boyfriend','stated','00pm','want','tell','say','feel','know','ll', 've']
    for word in empirical_sw:
        sw.add(word)
    return sw
    

# Determine keywords for all categories, the keyword was selected by the coefficent(weight) of the word in
# the trained logistic regression model,then show keywords by word cloud.If des_file is provided the dummy documents
# will be generated by grouping all those keywords together
# Input: 
#    vectorizer: the vectorizer used to convert text to BOW
#    model:      trained supervised model
#    le:         LabelEncoder of sklearn 
#    des_file:   the path of dummy documents, if not none will generate dummy documents.   
#    exclusive:  whether a word can only keyword of one class
#    norm:       whether normalize the weight
# Output:
#    dummy_text_list: list of string, each string is combination of keywords
#    selected_word_indexes: Matrix with dimensions class_num x vocab_num, the location of selected words will have value 1 

def show_word_linear(vectorizer,model,le,des_file = None,exclusive=False,norm=False):
    index_2_word_dict = reverse_dict(vectorizer.vocabulary_)
    class_num = len(le.classes_)
    vocab_num = len(vectorizer.vocabulary_)
    stopwords = set()
    model_coef = model.coef_
    if exclusive:
        for col in range(np.shape(model_coef)[1]):
            minor_class = np.where(model_coef[:,col]!=max(model_coef[:,col]))[0]
            model_coef[minor_class,col] = 0
    if norm:
         for row in range(np.shape(model_coef)[0]):
            model_coef[row] = (model_coef[row] - np.mean(model_coef[row])) / np.std(model_coef[row])
    if des_file:
        if os.path.exists(des_file):
            os.remove(des_file)
    dummy_text_list = []
    min_word_num = 300
    selected_word_indexes = np.zeros([class_num,vocab_num])
    for i in range(class_num):
        dummy_text = ''
        word_index = np.argpartition(model_coef[i,:],-min_word_num)[-min_word_num:]
        print(len(word_index))
        selected_word_indexes[i,word_index] = 1
        # The time of apprance of different keywords in dummy documents is decided by its coefficent
        for ind in word_index:
            dummy_text += (' '+index_2_word_dict[ind])*int(np.round(model_coef[i,ind]))
        if des_file:
            des = open(des_file,'a')
            des.writelines(le.classes_[i] +':\t'+ dummy_text + '\n')
        wordcloud = WordCloud(width = 1200,height=800,background_color="white",stopwords=stopwords).generate(dummy_text)
        plt.figure( figsize=(20,10) )
        plt.imshow(wordcloud, interpolation='bilinear')
        plt.axis("off")
        dummy_text_list.append(dummy_text)
        print(le.classes_[i])
    return dummy_text_list,selected_word_indexes
  
#Print the most likely words for given topics
# Input: 
#    topic_model: trained lda model
#    vectorizer:  the vectorizer used to convert text to BOW
#    word_num:    how many words you want to print
#    weight_list: List of number, the topic will be listed according to this list. In my code this list was generated by sorting the proportion of different LDA topics in the dataset    
# Output:
#    representative_words:  Matrix with dimensions topic_num x word_num, index of selected words
#    representative_weight: Matrix with dimensions topic_num x word_num, weight of selected words 
 
def print_topic_word(topic_model,vectorizer,word_num=20,weight_list=None):
    index_2_word_dict = reverse_dict(vectorizer.vocabulary_)
    topic_num = np.shape(topic_model.components_)[0]
    feature_num = len(vectorizer.vocabulary_)
    norm_score = topic_model.components_ / topic_model.components_.sum(axis=1)[:, np.newaxis]
    representative_words = np.zeros((topic_num,word_num),dtype=np.int32)
    representative_weight = np.zeros((topic_num,word_num))
    if not weight_list:
        for i in range(topic_num):
            tmp_score = norm_score[i,:]
            representative_words[i,:] = np.argsort(tmp_score)[-word_num:]
            representative_weight[i,:] = np.sort(tmp_score)[-word_num:]
            line = 'Topic '+str(i)
            for j in range(word_num-1,0,-1):
                line += ' ' + index_2_word_dict[representative_words[i,j]]+','
            print(line+'\n')
    else:
        for i in weight_list:
            tmp_score = norm_score[i,:]
            representative_words[i,:] = np.argsort(tmp_score)[-word_num:]
            representative_weight[i,:] = np.sort(tmp_score)[-word_num:]
            #import pdb;pdb.set_trace()
            line = 'Topic '+str(i)
            for j in range(word_num-1,0,-1):
                line += ' ' + index_2_word_dict[representative_words[i,j]]+','
            print(line+'\n')
    return representative_words,representative_weight

#Print documents that contains multiple concerns, The selection criterion was that 
#highest score among the classification results of LDA was not very high.
#Input:
#   topics_dist: topic distribution of all documents, dimension: number of documents x number of topics
#   raw_texts:   the raw text before converted into bow
#   ex_num:      how many example you want to display
def find_mixture(topics_dist,raw_text,ex_num=200):
	num,t_num = np.shape(topics_dist)
	score = np.zeros((num,))
	for i in range(num):
		score[i] = -max(topics_dist[i,:])
	sort_index = np.argsort(score)
	for i in range(-1,-ex_num,-1):
		print(raw_text[sort_index[i]])
		print(topics_dist[sort_index[i],:])
   
#Display representative documents for each topic
#Input:
#   docu_vec:    BOW matrix
#   lda_model:   trained LDA model
#   raw_text:    raw_text
#   map_to_unlemma: the indices of lemmatized and unlemmatized dataset are different. Use this to map the lemmatized docuemnt to the original ones for easy reading.
#   example_num:    how many example you want to display
#   thres：      a document must be assigned to a topic with at least this percentage to be selected
def show_lda_example(docu_vec,lda_model,raw_text,map_to_unlemma,example_num=5,thres=0.5):
    example_dict = defaultdict(list)
    topic_num = np.shape(lda_model.components_)[0]
    topic_assign = lda_model.transform(docu_vec)
    for i in range(np.shape(topic_assign)[0]):
        if max(topic_assign[i,:])>thres:
            example_dict[np.argmax(topic_assign[i,:])].append(map_to_unlemma[i])
    import random
    for i in range(topic_num):
        print('\nTopic '+ str(i))
        random.shuffle(example_dict[i])
        for j in range(min(example_num,len(example_dict[i]))):
            tmp_example = raw_text[example_dict[i][j]]
            print(str(j)+' : '+tmp_example+'\n'+str(example_dict[i][j])+'\n')

# Loss function consisting of entropy loss and correlation loss. 
# The NB is prefixed because the original supervised learning method was Naive bayes. 
# For the same reason, there are many variable names starting with NB, which are used to handle LDA models and supervised learning.
#Input:
#   y:      not used in the function, but must have this parameter to pass this function to the model selection module of sklearn 
#   Y_pred: predicted topic distribution for dummy documents, obtained by run lda.transform(bow_vector)
#Output:
#   loss: scalar
def NB_loss_function(y,Y_pred):
    import scipy 
    #import pdb; pdb.set_trace()
    loss = 0
    corr_loss = []
    for i in range(np.shape(Y_pred)[0]):
        tmp_corr = 0
        for j in range(i+1,np.shape(Y_pred)[0]):
            tmp_corr += Y_pred[i,:].dot(Y_pred[j,:])
        corr_loss.append(tmp_corr)
        loss -= scipy.stats.entropy(Y_pred[i,:])
    # Multiplying by a 10 is necessary in order to let the two losses to be on the same order of magnitude.
    # According to the experience of this project, the entropy loss floats between 4.0 - 8.0, and the
    # second loss floats between 0.15 - 0.6 before multiplying by 10.
    print('Entropy Loss: ' + str(loss))
    loss -= 10*np.sum(corr_loss)
    print('Corr Loss: ' + str(np.sum(corr_loss)))
    return loss
    
    
# prepare the matrix of bow for grid search of sklearn. The bow matrix formed by all patient concerns 
# and the bow matrix formed by the dummy document are stacked together, and their indices are passed to 
# gridsearch to split the "training" and "test" sets.
#Input:
#   vectorizer:     sklearn's vectorizer class
#   dummy_document: path of dummy documents
#Output:
#   total_vec:      BOW matrix, first N rows are from patient concerns, last 4 rows are from dummy documents 
#   myCViterator:   parameter passed to grid search
def total_vect_cv_prepare(vectorizer=None,dummy_document = 'NB_2'):
    if vectorizer is None:
        vectorizer,vec = default_bow()
    else:
        lemma_filtered_text = read_filtered_lemma_data()
        #import random
        vec = vectorizer.transform(lemma_filtered_text)
    NB_vect = NB_data_loader(dummy_document,vectorizer)
    total_vec = vstack([vec,NB_vect])
    train_len= np.shape(vec)[0]
    test_len = train_len+np.shape(NB_vect)[0]
    train_index = list(range(train_len))
    test_index = list(range(train_len,test_len))
    myCViterator = []
    myCViterator.append((train_index,test_index))
    return total_vec,myCViterator
    
def read_lemma_data():
    src_lines = open('lemmad_text').readlines()
    lemma_text = []
    for item in src_lines:
        lemma_text.append(item)
    return lemma_text

def read_filtered_lemma_data():
    src_lines = open('lemma_filtered_text').readlines()
    lemma_filtered_text = []
    for item in src_lines:
        lemma_filtered_text.append(item)
    return lemma_filtered_text

def NB_data_loader(NB_doc,count_vectorizer):
    #new_count_vectorizer = CountVectorizer(vocabulary=count_vectorizer.vocabulary_)
    src = open(NB_doc)
    src_lines = src.readlines()
    NB_list = []
    for line in src_lines:
        NB_list.append(line.split(':')[-1].strip())
    NB_vect = count_vectorizer.transform(NB_list)
    return NB_vect
    
def default_bow():
    sw = stop_word()
    lemma_filtered_text = read_filtered_lemma_data()
    Count_vectorizer =CountVectorizer(ngram_range=(1,1),min_df = 7,stop_words=sw,max_df = 0.8)
    Count_vec = Count_vectorizer.fit_transform(lemma_filtered_text)
    return Count_vectorizer,Count_vec
    
def read_labels():
    # read labels
    filename = '~/data/patient_report/all_patient_data.csv'
    df = pd.read_csv(filename)
    df['Primary / secondary category'].fillna(' ',inplace=True)
    df['Full action description'].fillna(' ',inplace=True)
    df2 = df[df['Primary / secondary category'] != ' ']
    df2 = df2[df2['Full action description'] != ' ']
    print(len(df2))
    subject = df2['Action subject'].fillna(' ').to_list()
    full_text = df2['Full action description'].fillna(' ').to_list()
    label = df2['Primary / secondary category'].fillna(' ').to_list()
    solution = df2['Resolution response'].fillna(' ').to_list()
    # encode labels
    le = preprocessing.LabelEncoder()
    primary =[]
    secondary=[]
    for i in range(len(label)):
        primary.append(label[i].split('-')[0])
        secondary.append(label[i].split('-')[1])
    print(len(primary))
    le.fit(primary)
    Y = le.transform(primary)
    return le,Y
    
def NB_data_prepare(vectorizer=None):
    if vectorizer is None:
        vectorizer,vec = default_bow()
    lemma_text = read_lemma_data()
    Count_vectorizer2 = CountVectorizer(vocabulary=vectorizer.vocabulary_)
    Count_vec_no_filtered = Count_vectorizer2.fit_transform(lemma_text)
    return vectorizer,Count_vec_no_filtered
    