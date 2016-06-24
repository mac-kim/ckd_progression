import tables
import numpy as np
import theano
import theano.tensor as T
from theano.tensor.nnet.conv import conv2d
from theano.tensor.signal.downsample import max_pool_2d
import pdb
import lasagne
import sklearn.metrics

random_seed = 345
srng = theano.tensor.shared_randomstreams.RandomStreams(seed=random_seed)

def get_data(in_fname):

	with tables.open_file(in_fname, mode='r') as fin:
		n_examples = fin.root.batch_input_train.nrows
		X_train = fin.root.batch_input_train[0:n_examples]
		Y_train = fin.root.batch_target_train[0:n_examples]
		X_validation = fin.root.batch_input_validation[0:n_examples]
		Y_validation = fin.root.batch_target_validation[0:n_examples]
		X_test = fin.root.batch_input_test[0:n_examples]
		Y_test = fin.root.batch_target_test[0:n_examples]

	return X_train, Y_train, X_validation, Y_validation, X_test, Y_test

def add_dropout(l, dropout, deterministic):
	if dropout > 0:
		if deterministic:
			l = dropout*l
		else:
			l = T.switch(srng.binomial(size=l.shape, p=(1. - dropout)), l, 0)
	return l

def get_prob(X, w1, w2, b2, w3, b3, pool_horiz, n_conv, dropout, deterministic):

	l1 = T.nnet.relu(conv2d(X, w1, border_mode='valid', subsample=(1, 1)))
	l2 = max_pool_2d(l1, ds=(1, pool_horiz), st=(1, 1), ignore_border=True)
	l3 = l2.reshape((X.shape[0], n_conv))	
	l3 = add_dropout(l3, dropout, deterministic)
	l4 = T.nnet.relu(T.dot(l3, w2) + b2)
	l4 = add_dropout(l4, dropout, deterministic)
	prob = T.nnet.softmax(T.dot(l4, w3) + b3)

	return prob

def build_model():

	X = T.tensor4()
	Y = T.itensor4()

	n_hidden = 100
	n_classes = 2
	n_filters = 8
	n_features = 15
	n_time = 12
	k_horiz = 8
	pool_horiz = 3
	dropout = 0
	
	tdim1 = 1 + n_time - k_horiz
	tdim2 = 1 + tdim1 - pool_horiz
	n_conv = int(n_filters*n_features*tdim2)

	w1 = theano.shared(value=np.asarray(np.random.randn(n_filters, 1, 1, k_horiz) * 0.01, dtype=theano.config.floatX))
	w2 = theano.shared(value=np.asarray(np.random.randn(n_conv, n_hidden) * 0.01, dtype=theano.config.floatX))
	b2 = theano.shared(value=np.asarray(np.random.randn(n_hidden) * 0.01, dtype=theano.config.floatX))
	w3 = theano.shared(value=np.asarray(np.random.randn(n_hidden, n_classes) * 0.01, dtype=theano.config.floatX))
	b3 = theano.shared(value=np.asarray(np.random.randn(n_classes) * 0.01, dtype=theano.config.floatX))

	prob = get_prob(X, w1, w2, b2, w3, b3, pool_horiz, n_conv, dropout, deterministic=False)
	test_prob = get_prob(X, w1, w2, b2, w3, b3, pool_horiz, n_conv, dropout, deterministic=True)

	#return theano.function(inputs=[X], outputs=l2, allow_input_downcast=True)

	prediction = T.argmax(prob, axis=1)
	train_loss = -T.mean(T.log(prob)[T.arange(X.shape[0]), Y[:,0,0,0]])

	params = [w1, w2, b2, w3, b3]
	updates = lasagne.updates.adadelta(train_loss, params, learning_rate=1.0, rho=0.95, epsilon=1e-06) 

	train_fn = theano.function(inputs=[X, Y], outputs=train_loss, updates=updates, allow_input_downcast=True)
	predict_fn = theano.function(inputs=[X], outputs=test_prob, allow_input_downcast=True) 

	return train_fn, predict_fn

def evaluate(X_train, Y_train, X_validation, Y_validation, X_test, Y_test):

	train_fn, predict_fn = build_model()

	n_epochs = 1
	mini_batch_size = 256
	n_examples = X_train.shape[0]

	for epoch in range(n_epochs):
		print epoch
		for start, stop in zip(range(0, n_examples, mini_batch_size), range(mini_batch_size, n_examples, mini_batch_size)):
			train_loss = train_fn(X_train[start:stop], Y_train[start:stop])

	proba = predict_fn(X_test)[:,1]
	fpr, tpr, _ = sklearn.metrics.roc_curve(Y_test[:,0,0,0], proba)
	auc = sklearn.metrics.auc(fpr, tpr)	
	print auc

