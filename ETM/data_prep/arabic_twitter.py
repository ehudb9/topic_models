# same code as in data_nyt.py, but for handeling arabic data
from sklearn.feature_extraction.text import CountVectorizer
import numpy as np
import pickle
from scipy import sparse
from scipy.io import savemat, loadmat
import os
import re


class ArabicTwitterPreProcess(object):
    def __init__(self, config_dict, machine='AVRAHAMI-PC'):
        self.config_dict = config_dict
        self.machine = machine
        self.cvectorizer_obj = None
        self.vocab = None
        self.word2id = None
        self.id2word = None

    def fit_transform(self, data_path, verbose=True):
        # Read stopwords, taken from here - https://github.com/mohataher/arabic-stop-words/blob/master/list.txt
        with open('stops_arabic.txt', 'r', encoding='utf-8') as f:
            stops = f.read().split('\n')

        docs = self._load_data(data_path=data_path)
        # Create count vectorizer
        cvectorizer = CountVectorizer(min_df=self.config_dict['data_prep_params']['min_df'],
                                      max_df=self.config_dict['data_prep_params']['max_df'],
                                      stop_words=None)
        cvz = cvectorizer.fit_transform(docs).sign()
        self.cvectorizer_obj = cvectorizer

        # Get vocabulary
        sum_counts = cvz.sum(axis=0)
        v_size = sum_counts.shape[1]
        sum_counts_np = np.zeros(v_size, dtype=int)
        for v in range(v_size):
            sum_counts_np[v] = sum_counts[0, v]
        word2id = dict([(w, cvectorizer.vocabulary_.get(w)) for w in cvectorizer.vocabulary_])
        id2word = dict([(cvectorizer.vocabulary_.get(w), w) for w in cvectorizer.vocabulary_])
        if verbose:
            print(' initial vocabulary size: {}'.format(v_size))

        # Sort elements in vocabulary
        idx_sort = np.argsort(sum_counts_np)
        vocab_aux = [id2word[idx_sort[cc]] for cc in range(v_size)]

        # Filter out stopwords (if any)
        vocab_aux = [w for w in vocab_aux if w not in stops]
        if verbose:
            print('  vocabulary size after removing stopwords from list: {}'.format(len(vocab_aux)))
            print('  vocabulary after removing stopwords: {}'.format(len(vocab_aux)))

        # Create dictionary and inverse dictionary
        vocab = vocab_aux
        word2id = dict([(w, j) for j, w in enumerate(vocab)])
        id2word = dict([(j, w) for j, w in enumerate(vocab)])

        #  Split in train/test/valid
        num_docs = cvz.shape[0]
        trSize = int(np.floor(0.85 * num_docs))
        tsSize = int(np.floor(0.10 * num_docs))
        vaSize = int(num_docs - trSize - tsSize)
        idx_permute = np.random.permutation(num_docs).astype(int)

        #  Remove words not in train_data
        vocab = list(set([w for idx_d in range(trSize) for w in docs[idx_permute[idx_d]].split() if w in word2id]))
        word2id = dict([(w, j) for j, w in enumerate(vocab)])
        id2word = dict([(j, w) for j, w in enumerate(vocab)])
        self.vocab = vocab
        self.id2word = id2word
        self.word2id = word2id
        if verbose:
            print(f' vocabulary after removing words not in train: {len(vocab)}')

        docs_tr = [[word2id[w] for w in docs[idx_permute[idx_d]].split() if w in word2id] for idx_d in range(trSize)]
        docs_ts = [[word2id[w] for w in docs[idx_permute[idx_d + trSize]].split() if w in word2id] for idx_d in
                   range(tsSize)]
        docs_va = [[word2id[w] for w in docs[idx_permute[idx_d + trSize + tsSize]].split() if w in word2id] for idx_d in
                   range(vaSize)]
        del docs
        if verbose:
            print(f' number of documents (train): {len(docs_tr)} [this should be equal to {trSize}]')
            print(f' number of documents (test): {len(docs_ts)} [this should be equal to {tsSize}]')
            print(f' number of documents (valid): {len(docs_va)} [this should be equal to {vaSize}]')

        #  Remove empty documents
        docs_tr = self.remove_empty(docs_tr)
        docs_ts = self.remove_empty(docs_ts)
        docs_va = self.remove_empty(docs_va)

        # Remove test documents with length=1
        docs_ts = [doc for doc in docs_ts if len(doc) > 1]

        # Split test set in 2 halves
        docs_ts_h1 = [[w for i, w in enumerate(doc) if i <= len(doc) / 2.0 - 1] for doc in docs_ts]
        docs_ts_h2 = [[w for i, w in enumerate(doc) if i > len(doc) / 2.0 - 1] for doc in docs_ts]

        # Getting lists of words and doc_indices
        words_tr = self.create_list_words(docs_tr)
        words_ts = self.create_list_words(docs_ts)
        words_ts_h1 = self.create_list_words(docs_ts_h1)
        words_ts_h2 = self.create_list_words(docs_ts_h2)
        words_va = self.create_list_words(docs_va)

        if verbose:
            print(' len(words_tr): ', len(words_tr))
            print(' len(words_ts): ', len(words_ts))
            print(' len(words_ts_h1): ', len(words_ts_h1))
            print(' len(words_ts_h2): ', len(words_ts_h2))
            print(' len(words_va): ', len(words_va))

        # Get doc indices
        doc_indices_tr = self.create_doc_indices(docs_tr)
        doc_indices_ts = self.create_doc_indices(docs_ts)
        doc_indices_ts_h1 = self.create_doc_indices(docs_ts_h1)
        doc_indices_ts_h2 = self.create_doc_indices(docs_ts_h2)
        doc_indices_va = self.create_doc_indices(docs_va)

        if verbose:
            print(f' len(np.unique(doc_indices_tr)): {len(np.unique(doc_indices_tr))} [this should be {len(docs_tr)}]')
            print(f' len(np.unique(doc_indices_ts)): {len(np.unique(doc_indices_ts))} [this should be {len(docs_ts)}]')
            print(f' len(np.unique(doc_indices_ts_h1)): {len(np.unique(doc_indices_ts_h1))} '
                  f'[this should be {len(docs_ts_h1)}]')
            print(f' len(np.unique(doc_indices_ts_h2)): {len(np.unique(doc_indices_ts_h2))} '
                  f'[this should be {len(docs_ts_h2)}]')
            print(f' len(np.unique(doc_indices_va)): {len(np.unique(doc_indices_va))} [this should be {len(docs_va)}]')

        # Number of documents in each set
        n_docs_tr = len(docs_tr)
        n_docs_ts = len(docs_ts)
        n_docs_ts_h1 = len(docs_ts_h1)
        n_docs_ts_h2 = len(docs_ts_h2)
        n_docs_va = len(docs_va)

        # Remove unused variables
        del docs_tr, docs_ts, docs_ts_h1, docs_ts_h2, docs_va

        # Create bow representation
        bow_tr = self.create_bow(doc_indices_tr, words_tr, n_docs_tr, len(vocab))
        bow_ts = self.create_bow(doc_indices_ts, words_ts, n_docs_ts, len(vocab))
        bow_ts_h1 = self.create_bow(doc_indices_ts_h1, words_ts_h1, n_docs_ts_h1, len(vocab))
        bow_ts_h2 = self.create_bow(doc_indices_ts_h2, words_ts_h2, n_docs_ts_h2, len(vocab))
        bow_va = self.create_bow(doc_indices_va, words_va, n_docs_va, len(vocab))

        del words_tr, words_ts, words_ts_h1, words_ts_h2, words_va, doc_indices_tr, doc_indices_ts
        del doc_indices_ts_h1, doc_indices_ts_h2, doc_indices_va

        # Save vocabulary to file
        # path_save = './min_df_' + str(min_df) + '/'
        path_save = os.path.join(self.config_dict['saving_data_path'][self.machine], self.config_dict['dataset'], '')
        if not os.path.isdir(path_save):
            os.system('mkdir -p ' + path_save)

        with open(path_save + 'vocab.pkl', 'wb') as f:
            pickle.dump(vocab, f)

        # Split bow into token/value pairs
        bow_tr_tokens, bow_tr_counts = self.split_bow(bow_tr, n_docs_tr)
        savemat(path_save + 'bow_tr_tokens.mat', {'tokens': bow_tr_tokens}, do_compression=True)
        savemat(path_save + 'bow_tr_counts.mat', {'counts': bow_tr_counts}, do_compression=True)
        del vocab, bow_tr, bow_tr_tokens, bow_tr_counts

        bow_ts_tokens, bow_ts_counts = self.split_bow(bow_ts, n_docs_ts)
        savemat(path_save + 'bow_ts_tokens.mat', {'tokens': bow_ts_tokens}, do_compression=True)
        savemat(path_save + 'bow_ts_counts.mat', {'counts': bow_ts_counts}, do_compression=True)
        del bow_ts, bow_ts_tokens, bow_ts_counts

        bow_ts_h1_tokens, bow_ts_h1_counts = self.split_bow(bow_ts_h1, n_docs_ts_h1)
        savemat(path_save + 'bow_ts_h1_tokens.mat', {'tokens': bow_ts_h1_tokens}, do_compression=True)
        savemat(path_save + 'bow_ts_h1_counts.mat', {'counts': bow_ts_h1_counts}, do_compression=True)
        del bow_ts_h1, bow_ts_h1_tokens, bow_ts_h1_counts

        bow_ts_h2_tokens, bow_ts_h2_counts = self.split_bow(bow_ts_h2, n_docs_ts_h2)
        savemat(path_save + 'bow_ts_h2_tokens.mat', {'tokens': bow_ts_h2_tokens}, do_compression=True)
        savemat(path_save + 'bow_ts_h2_counts.mat', {'counts': bow_ts_h2_counts}, do_compression=True)
        del bow_ts_h2, bow_ts_h2_tokens, bow_ts_h2_counts

        bow_va_tokens, bow_va_counts = self.split_bow(bow_va, n_docs_va)
        savemat(path_save + 'bow_va_tokens.mat', {'tokens': bow_va_tokens}, do_compression=True)
        savemat(path_save + 'bow_va_counts.mat', {'counts': bow_va_counts}, do_compression=True)
        del bow_va, bow_va_tokens, bow_va_counts
        if verbose:
            print(f'Data is ready !! All data has been saved in {path_save}')

    def transform(self, data_path):
        docs = self._load_data(data_path=data_path)
        n_docs_new_val = len(docs)
        docs_new_val = [[self.word2id[w] for w in docs[idx_d].split() if w in self.word2id] for idx_d in range(n_docs_new_val)]
        docs_new_val = self.remove_empty(docs_new_val)
        # Remove  documents with length=1
        docs_new_val = [doc for doc in docs_new_val if len(doc) > 1]
        print(f'Number of valid documents: {len(docs_new_val)}')
        words_new_val = self.create_list_words(docs_new_val)
        doc_indices_new_val = self.create_doc_indices(docs_new_val)
        n_docs_new_val = len(docs_new_val)
        bow_new_val = self.create_bow(doc_indices_new_val, words_new_val, n_docs_new_val, len(self.vocab))
        bow_new_val_tokens, bow_new_val_counts = self.split_bow(bow_new_val, n_docs_new_val)
        path_save = os.path.join(self.config_dict['saving_data_path'][self.machine], self.config_dict['dataset'], '')
        if not os.path.isdir(path_save):
            os.system('mkdir -p ' + path_save)
        savemat(path_save + 'bow_new_val_tokens.mat', {'tokens': bow_new_val_tokens}, do_compression=True)
        savemat(path_save + 'bow_new_val_counts.mat', {'counts': bow_new_val_counts}, do_compression=True)
        tokens = loadmat(os.path.join(path_save, 'bow_new_val_tokens.mat'))['tokens'].squeeze()
        counts = loadmat(os.path.join(path_save, 'bow_new_val_counts.mat'))['counts'].squeeze()
        return tokens, counts

    def _load_data(self, data_path):
        # find all files ending with .p (pickle files)
        data_file_names = [f for f in os.listdir(data_path) if re.match(r'.*.p', f)]
        if len(data_file_names) == 0:
            raise IOError(f"Not even a single pickle file has been found in {data_path}. Check again.")
        docs = []
        for cur_file in data_file_names:
            intuview_data_as_dict = pickle.load(open(os.path.join(data_path, cur_file), "rb"))
            # docs is a list of threads
            cur_docs = self._convert_intuview_dict_to_docs_list(intuview_data=intuview_data_as_dict)
            docs.extend(cur_docs)
        return docs

    def save_obj(self, f_name):
        pickle.dump(self, open(os.path.join(self.config_dict['saving_models_path'][self.machine], f_name), "wb"))

    @staticmethod
    def load_obj(f_path, f_name):
        pre_process_obj = pickle.load(open(os.path.join(f_path, f_name), "rb"))
        return pre_process_obj

    @staticmethod
    def _convert_intuview_dict_to_docs_list(intuview_data):
        docs_list = list()
        for loop_idx, (main_post_id, main_post_values) in enumerate(intuview_data.items()):
            cur_thread_full_text = main_post_values['main_post']['text']
            # looping over all responses, extracting the text and tonenazing them
            for child_key, child_values in main_post_values['responses'].items():
                cur_child_text = child_values['text']
                cur_thread_full_text += '. ' + cur_child_text
            docs_list.append(cur_thread_full_text)
        return docs_list

    @staticmethod
    def create_list_words(in_docs):
        return [x for y in in_docs for x in y]

    @staticmethod
    def remove_empty(in_docs):
        return [doc for doc in in_docs if doc != []]

    @staticmethod
    def create_doc_indices(in_docs):
        """

        :param in_docs: list of lists (size: number_documents X len(words) in each document)
        :return: list (size: number_documents X len(words) in each document)
            long list full with integer. The first n places will be filled with zeros (n=length of the first doc)
            The next k places (after the n ones) will be filled with 1's (k=length of the second doc)
            and so on...
        """
        aux = [[j for i in range(len(doc))] for j, doc in enumerate(in_docs)]
        return [int(x) for y in aux for x in y]

    @staticmethod
    def create_bow(doc_indices, words, n_docs, vocab_size):
        return sparse.coo_matrix(([1] * len(doc_indices), (doc_indices, words)), shape=(n_docs, vocab_size)).tocsr()

    @staticmethod
    def split_bow(bow_in, n_docs):
        indices = [[w for w in bow_in[doc, :].indices] for doc in range(n_docs)]
        counts = [[c for c in bow_in[doc, :].data] for doc in range(n_docs)]
        return indices, counts

