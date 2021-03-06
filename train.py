import sys

import tensorflow as tf
from tensorflow.python.ops import math_ops

sys.path.append("slim/")

slim = tf.contrib.slim

TRAIN_DIR = "/tmp/tf"


class Trainer(object):
  def __init__(self, nb_classes, optimizer, learning_rate):
    self.nb_classes = nb_classes
    # learning rate can be a placeholder tensor
    self.learning_rate = learning_rate
    self.optimizer = optimizer(learning_rate)
    self.train_op = None
    self.prediction = None

  def build(self, predictions, labels, one_hot=False):
    with tf.name_scope('training'):
      if one_hot:
        labels = tf.one_hot(labels, depth=self.nb_classes)
        labels = tf.squeeze(labels, axis=2)
        label_shape = tf.shape(labels)[:2]
        predictions = tf.image.resize_bilinear(predictions, label_shape, name='resize_predictions')
      else:
        labels = tf.reshape(labels, (-1, self.nb_clasess))
        predictions = tf.reshape(predictions, (-1, self.nb_classes))
      self.prediction = predictions
      labels = tf.expand_dims(labels, 0)
      print("pred shape {}, label shape {}".format(predictions.get_shape(), labels.get_shape()))
      # wraps the softmax_with_entropy fn. adds it to loss collection
      tf.losses.softmax_cross_entropy(logits=predictions, onehot_labels=labels)
      # include the regulization losses in the loss collection.
      total_loss = tf.losses.get_total_loss()
      self.train_op = slim.learning.create_train_op(total_loss,
                                                    optimizer=self.optimizer)
  def add_summaries(self):
    # Add summaries for images, variables and losses.
    global_summaries = set([])
    # image summary
    image_summary = tf.get_default_graph().get_tensor_by_name('IteratorGetNext:0')
    image_summary = tf.expand_dims(image_summary, 0)
    image_summary = tf.summary.image('image', image_summary)
    global_summaries.add(image_summary)
    # prediction summary
    prediction = tf.argmax(self.prediction, axis=3)
    prediction = tf.cast(prediction, tf.float32)
    prediction = tf.expand_dims(prediction, 3)
    image_summary = tf.summary.image('prediction', prediction)
    global_summaries.add(image_summary)
    for model_var in slim.get_model_variables():
      global_summaries.add(tf.summary.histogram(model_var.op.name, model_var))
    # total loss
    total_loss_tensor = tf.get_default_graph().get_tensor_by_name('training/total_loss:0')
    global_summaries.add(tf.summary.scalar(total_loss_tensor.op.name, total_loss_tensor))
    # Merge all summaries together.
    summary_op = tf.summary.merge(list(global_summaries), name='summary_op')
    return summary_op

  def train(self, iterator,
            filename,
            restore_fn=None,
            _add_summaries = True,
            number_of_steps=10000,
            save_interval_secs = 12000,
            same_summaries_secs=120,
            keep_checkpoint_every_n_hours=5):
    summary_op = None
    if _add_summaries:
      summary_op = self.add_summaries()
    # Save checkpoints regularly.
    saver = tf.train.Saver(
        keep_checkpoint_every_n_hours=keep_checkpoint_every_n_hours)
    # init fn for the dataset ops and checkpointin
    def initializer_fn(sess):
        input_tensor = tf.get_default_graph().get_tensor_by_name('training_data/input:0')
        sess.run(iterator.initializer, feed_dict={input_tensor: filename})
        if restore_fn:
          restore_fn(sess)
    init_fn = initializer_fn
    # Soft placement allows placing on CPU ops without GPU implementation.
    session_config = tf.ConfigProto(allow_soft_placement=True,
                                    log_device_placement=False)
    # train
    slim.learning.train(train_op=self.train_op,
                        logdir=TRAIN_DIR,
                        session_config=session_config,
                        summary_op=summary_op,
                        init_fn=init_fn,
                        save_interval_secs = save_interval_secs,
                        number_of_steps=number_of_steps,
                        save_summaries_secs=same_summaries_secs,
                        saver=saver)
