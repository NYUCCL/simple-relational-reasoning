import argparse
import os
import sys

sys.path.append(os.path.abspath('..'))

from simple_relational_reasoning import models


parser = argparse.ArgumentParser()

# Running-related arguments

DEFAULT_SEED = 33
parser.add_argument('--seed', type=int, default=DEFAULT_SEED, help='Random seed to run with')

DEFAULT_MAX_EPOCHS = 10000
parser.add_argument('--max-epochs', type=int, default=DEFAULT_MAX_EPOCHS, help='After how many epochs should we stop')

DEFAULT_BATCH_SIZE = 2 ** 8
parser.add_argument('--batch-size', type=int, default=DEFAULT_BATCH_SIZE,
                    help='Batch size to run with')

DEFAULT_LEARNING_RATE = 1e-3
parser.add_argument('--learning-rate', type=float, default=DEFAULT_LEARNING_RATE,
                    help='Learning rate to run with')

DEFAULT_PATIENCE_EPOCHS = 50
parser.add_argument('--patience-epochs', type=int, default=DEFAULT_PATIENCE_EPOCHS,
                    help='How many patience epochs (stop after this many epochs with no improvement)')

DEFAULT_MIN_DELTA = 1e-5
parser.add_argument('--early-stopping-min-delta', type=float, default=DEFAULT_MIN_DELTA,
                    help='What minimal improvement in the metric to consider as an actualy improvement')

# Quinn object generator arguments

parser.add_argument('--use_object_size', type=int, default=None, help='Whether or not to use object sizes')

DEFAULT_REFERENCE_OBJECT_LENGTH = 9
parser.add_argument('--reference_object_length', type=int, default=DEFAULT_REFERENCE_OBJECT_LENGTH,
                    help='Reference object (horizontal) length')

DEFAULT_TARGET_OBJECT_LENGTH = 1
parser.add_argument('--target_object_length', type=int, default=DEFAULT_TARGET_OBJECT_LENGTH,
                    help='Target object (horizontal) length')

DEFAULT_N_REFERENCE_OBJECT_TYPES = 1
parser.add_argument('--n_reference_object_types', type=int, default=DEFAULT_N_REFERENCE_OBJECT_TYPES,
                    help='Number of reference object types to use')

DEFAULT_N_TRAIN_TARGET_OBJECT_TYPES = 1
parser.add_argument('--n_train_target_object_types', type=int, default=DEFAULT_N_TRAIN_TARGET_OBJECT_TYPES,
                    help='Number of target object types to use in training (and in test if n_train_target_object_types = 0)')

DEFAULT_N_TEST_TARGET_OBJECT_TYPES = 0
parser.add_argument('--n_test_target_object_types', type=int, default=DEFAULT_N_TEST_TARGET_OBJECT_TYPES,
                    help='Number of target object types to use in test')

# Quinn dataset arguments

DEFAULT_X_MAX = 20
parser.add_argument('--x_max', type=int, default=DEFAULT_X_MAX, help='Canvas X size')

DEFAULT_Y_MAX = 20
parser.add_argument('--y_max', type=int, default=DEFAULT_Y_MAX, help='Canvas Y size')

DEFAULT_ADD_NEITHER_TRAIN = True
parser.add_argument('--add_neither_train', type=int, default=DEFAULT_ADD_NEITHER_TRAIN,
                    help='Add examples of neither (off to the side) in the training set')

DEFAULT_ADD_NEITHER_TEST = False
parser.add_argument('--add_neither_test', type=int, default=DEFAULT_ADD_NEITHER_TEST,
                    help='Add examples of neither (off to the side) in the test set(s)')

DEFAULT_PROP_TRAIN_REFERENCE_OBJECT_LOCATIONS = 0.8
parser.add_argument('--prop_train_reference_object_locations', type=float,
                    default=DEFAULT_PROP_TRAIN_REFERENCE_OBJECT_LOCATIONS,
                    help='Proportion of reference object locations to assign to the training set')

DEFAULT_REFERENCE_OBJECT_X_MARGIN = 0
parser.add_argument('--reference_object_x_margin', type=int, default=DEFAULT_REFERENCE_OBJECT_X_MARGIN,
                    help='Horizontal margin to allow between the reference object and the edge of the canvas')

DEFAULT_REFERENCE_OBJECT_BOTTOM_Y_MARGIN = 0
parser.add_argument('--reference_object_bottom_y_margin', type=int, default=DEFAULT_REFERENCE_OBJECT_BOTTOM_Y_MARGIN,
                    help='Bottom vertical margin to allow between the reference object and the edge of the canvas')

DEFAULT_REFERENCE_OBJECT_TOP_Y_MARGIN = 0
parser.add_argument('--reference_object_top_y_margin', type=int, default=DEFAULT_REFERENCE_OBJECT_TOP_Y_MARGIN,
                    help='Top vertical margin to allow between the reference object and the edge of the canvas')

# Paradigm-related arguments

PARADIGMS = (
    'inductive_bias',
    'one_or_two_references'
)
parser.add_argument('--paradigm', type=str, action='append', choices=PARADIGMS,
                    help='Which paradigm to run')

RELATIONS = (
    'above_below',
    'between'
)
parser.add_argument('--relation', type=str, action='append', choices=RELATIONS,
                    help='Which relation(s) to run (default: all)')

# Inductive bias paradigm arguments
DEFAULT_TARGET_OBJECT_GRID_SIZE = 3
parser.add_argument('--target_object_grid_size', type=int, default=DEFAULT_TARGET_OBJECT_GRID_SIZE,
                    help='Size of grid to assign target objects to (defaults to 3x3)')


DEFAULT_N_TRAIN_TARGET_OBJECT_LOCATIONS = None
parser.add_argument('--n_train_target_object_locations', type=int, default=DEFAULT_N_TRAIN_TARGET_OBJECT_LOCATIONS,
                    help='How many target object locations to assign to train (defaults to n * (n - 1) for an n x n grid)')

DEFAULT_ABOVE_OR_BETWEEN_LEFT = None
parser.add_argument('--above_or_between_left', type=int, default=DEFAULT_ABOVE_OR_BETWEEN_LEFT,
                    help='Which side to assign a particular class (above in above/below, between when it is in). Defaults to parity of the seed')


# One or two reference objects paradigm arguments

DEFAULT_TWO_REFERENCE_OBJECTS = None
parser.add_argument('--two_reference_objects', type=int, default=DEFAULT_TWO_REFERENCE_OBJECTS,
                    help='Whether or not to use two reference objects. Defaults to True for the between relation and False for above/below.')


# Model setup arguments

DEFAULT_MODELS_CONFIG_KEY = 'default'
LARGER_MODELS_CONFIG_KEY = 'larger'
MODEL_CONFIGURATIONS = {
    DEFAULT_MODELS_CONFIG_KEY: {
        models.CombinedObjectMLPModel: dict(embedding_size=8, prediction_sizes=[32, 32]),
        models.RelationNetModel: dict(embedding_size=8, object_pair_layer_sizes=[32], combined_object_layer_sizes=[32]),
        models.TransformerModel: dict(embedding_size=8, transformer_mlp_sizes=[8], mlp_sizes=[32]),
        models.CNNModel: dict(conv_sizes=[16, 16], conv_output_size=256),
        models.FixedCNNModel: dict(conv_sizes=[6, 6], conv_output_size=96, mlp_sizes=[16, 16],),
    },
    LARGER_MODELS_CONFIG_KEY: {
        models.CombinedObjectMLPModel: dict(embedding_size=16, prediction_sizes=[64, 32, 16]),
        models.RelationNetModel: dict(embedding_size=16, object_pair_layer_sizes=[64, 32],
                                      combined_object_layer_sizes=[64, 32]),
        models.TransformerModel: dict(embedding_size=16, num_transformer_layers=2, num_heads=2,
                                      transformer_mlp_sizes=[32, 16], mlp_sizes=[64, 32]),
        models.CNNModel: dict(conv_sizes=[8, 12, 16], conv_output_size=64, mlp_sizes=[32, 32, 32],),
        models.FixedCNNModel: dict(conv_sizes=[6, 6], conv_output_size=96, mlp_sizes=[16, 16],),
    }
}
parser.add_argument('--model-configuration', type=str, action='append', choices=list(MODEL_CONFIGURATIONS.keys()),
                    help='Which model configuration to use')


CLASS_NAME_SPLIT_WORDS = ('net', 'object', 'mlp', 'cnn')


def prettify_class_name(cls):
    name = cls.__name__.lower().replace('model', '')
    for word in CLASS_NAME_SPLIT_WORDS:
        name = name.replace(word, f'-{word}')

    if name.startswith('-'):
        return name[1:]

    return name


MODEL_NAMES = [prettify_class_name(model_class) for model_class in MODEL_CONFIGURATIONS['default'].keys()]
parser.add_argument('--model', type=str, action='append', choices=MODEL_NAMES,
                    help='Which model(s) to use (default: all)')


# Wandb-related arguments
SCRATCH_FOLDER = r'/misc/vlgscratch4/LakeGroup/guy/'

DEFUALT_WANDB_ENTITY = 'simple-relational-reasoning'
parser.add_argument('--wandb-entity', default=DEFUALT_WANDB_ENTITY)

DEFAULT_WANDB_DIR = SCRATCH_FOLDER  # wandb creates its own folder inside
parser.add_argument('--wandb-dir', default=DEFAULT_WANDB_DIR)
parser.add_argument('--wandb-omit-watch', action='store_true')


parser.add_argument('--wandb-project-suffix', type='str', default='')

# Handling fields with multiple potential options
MULTIPLE_OPTION_FIELD_DEFAULTS = {
    'model_configuration': [DEFAULT_MODELS_CONFIG_KEY],
    'model': MODEL_NAMES,
    'paradigm': PARADIGMS,
    'relation': RELATIONS,
    'use_object_size': [0, 1],
    'add_neither_train': [0, 1],
    'add_neither_test': [0, 1],
}

MULTIPLE_OPTION_REWRITE_FIELDS = list(MULTIPLE_OPTION_FIELD_DEFAULTS.keys())
MULTIPLE_OPTION_REWRITE_FIELDS.remove('model')  # intentionally no rewrite the model field downstream


def handle_multiple_option_defaults(args):
    var_args = vars(args)
    for key in MULTIPLE_OPTION_FIELD_DEFAULTS:
        if key not in var_args or var_args[key] is None or len(var_args[key]) == 0:
            var_args[key] = MULTIPLE_OPTION_FIELD_DEFAULTS[key]

        elif not hasattr(var_args[key], '__len__'):
            var_args[key] = [var_args[key]]

    return args

