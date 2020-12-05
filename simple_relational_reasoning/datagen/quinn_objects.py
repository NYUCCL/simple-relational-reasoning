from collections import defaultdict
import itertools

import numpy as np
import torch


"""
Idea:
We have a dataset generator object that:
- receives a random seed
- generates a single training set (inherits from `torch.utils.data.Dataset`)
- generates one or more test sets (also inherit from the same)

Questions:
- Do we ever have a y size? That is, height?
- How systematic do I want to be with held out locations?
    - For example, with the grid, do I hold out a location in one row or one column?
    - Same with the reference object locations, do I hold out systematically or randomly? 
- Do we care about testing "neither"? Or not really?
- Do we want distractor objects? Or are we okay without them?
    Start without, think about whether or not we need to add.
- Dataset size
    Aim for 4k-16k 
- Different train-test objects
    Use 1 for train and the same for test
    Use 1 for train and one for test
    Use 4 for train and a unique one for test
- Implement PrediNet at some point
- Pre-trained models:
    Quinn-like stimuli, per-trained models, embeding similarities in triplets  

Try both:
- Do we represent objects with a size? Or as a collection of size one objects?
- Do we always also introduce a "neither" class? 
    Try with and without, see what happens

"""


class ObjectGenerator:
    def __init__(self, seed, reference_object_length, target_object_length=1, n_reference_types=1,
                 n_train_target_types=1, n_test_target_types=0, n_non_type_fields=None, dtype=torch.float):
        self.seed = seed
        self.reference_object_length = reference_object_length
        self.target_object_length = target_object_length
        self.n_reference_types = n_reference_types
        self.n_train_target_types = n_train_target_types
        self.n_test_target_types = n_test_target_types
        self.n_types = self.n_reference_types + self.n_train_target_types + self.n_test_target_types
        self.n_non_type_fields = n_non_type_fields
        self.dtype = dtype

        self.rng = np.random.default_rng(self.seed)

    def reference_object(self, x, y, train=True):
        raise NotImplementedError()

    def target_object(self, x, y, train=True):
        raise NotImplementedError()

    def _sample_type(self, target=False, train=True):
        if not target:  # reference
            if self.n_reference_types <= 1:
                return 0

            return self.rng.integers(self.n_reference_types)

        if train or self.n_test_target_types == 0:
            if self.n_train_target_types <= 1:
                return self.n_reference_types  # 0-based, so this is the first index

            return self.rng.integers(self.n_reference_types, self.n_reference_types + self.n_train_target_types)

        # test and we have test only target types
        if self.n_test_target_types == 1:
            return self.n_reference_types + self.n_train_target_types  # 0-based, so this is the first one

        return self.rng.integers(self.n_reference_types + self.n_train_target_types, self.n_types)

    def _to_one_hot(self, n, n_types):
        one_hot = np.zeros(n_types)
        one_hot[n] = 1
        return one_hot

    def _sample_type_one_hot(self, target=False, train=True):
        return self._to_one_hot(self._sample_type(target, train), self.n_types)

    def get_type_slice(self):
        return slice(self.n_non_type_fields, self.n_non_type_fields + self.n_types)


class ObjectGeneratorWithSize(ObjectGenerator):
    def __init__(self, seed, reference_object_length, target_object_length=1, n_reference_types=1,
                 n_train_target_types=1, n_test_target_types=0, dtype=torch.float):
        super(ObjectGeneratorWithSize, self).__init__(seed, reference_object_length, target_object_length,
                                                      n_reference_types, n_train_target_types, n_test_target_types,
                                                      n_non_type_fields=3, dtype=dtype)

    def reference_object(self, x, y, train=True):
        return torch.tensor([x, y, self.reference_object_length, *self._sample_type_one_hot(False, train)],
                            dtype=self.dtype).unsqueeze(0)

    def target_object(self, x, y, train=True):
        return torch.tensor([x, y, self.target_object_length, *self._sample_type_one_hot(True, train)],
                            dtype=self.dtype).unsqueeze(0)


class ObjectGeneratorWithoutSize(ObjectGenerator):
    def __init__(self, seed, reference_object_length, target_object_length=1, n_reference_types=1,
                 n_train_target_types=1, n_test_target_types=0, dtype=torch.float):
        super(ObjectGeneratorWithoutSize, self).__init__(seed, reference_object_length, target_object_length,
                                                         n_reference_types, n_train_target_types, n_test_target_types,
                                                         n_non_type_fields=2, dtype=dtype)

    def reference_object(self, x, y, train=True):
        object_type = self._sample_type_one_hot(False, train)
        return torch.cat([torch.tensor([x + j, y, *object_type],
                                       dtype=self.dtype).unsqueeze(0)
                          for j in range(self.reference_object_length)])

    def target_object(self, x, y, train=True):
        object_type = self._sample_type_one_hot(True, train)
        return torch.cat([torch.tensor([x + j, y, *object_type],
                                       dtype=self.dtype).unsqueeze(0)
                          for j in range(self.target_object_length)])


class MinimalDataset(torch.utils.data.Dataset):
    def __init__(self, objects, labels, object_generator):
        super(MinimalDataset, self).__init__()

        if not isinstance(objects, torch.Tensor):
            objects = torch.stack(objects)

        if not isinstance(labels, torch.Tensor):
            labels = torch.tensor(labels)

        self.objects = objects
        self.labels = labels
        self.object_generator = object_generator

    def __getitem__(self, item):
        return self.objects[item], self.labels[item]

    def __len__(self):
        return self.objects.shape[0]

    def get_object_size(self):
        return self.objects.shape[-1]

    def get_num_objects(self):
        return self.objects.shape[1]

    def get_num_classes(self):
        return len(self.labels.unique())


class MinimalSpatialDataset(MinimalDataset):
    def __init__(self, objects, labels, object_generator, x_max, y_max, position_indices=(0, 1)):
        super(MinimalSpatialDataset, self).__init__(objects, labels, object_generator)

        D, N, O = self.objects.shape

        position_shape = (x_max, y_max)
        spatial_shape = (D, O, *position_shape)
        spatial_objects = torch.zeros(spatial_shape, dtype=self.objects.dtype)
        for ex_index in range(D):
            position_lists = [self.objects[ex_index, :, index].long()
                              for index in position_indices]

            # if torch.any(position_lists[0] > 24) or torch.any(position_lists[1] > 24) or self.objects[ex_index].max() > 24:
                # print('*' * 33 + ' FOUND ' + '*' * 33)
                # print(self.objects[ex_index])
                # print(position_lists[0])
                # print(position_lists[1])

            if len(position_lists) == 1:
                spatial_objects[ex_index, :, position_lists[0]] = self.objects[ex_index].transpose(0, 1)  #.unsqueeze(-1)

            elif len(position_lists) == 2:
                # try:
                spatial_objects[ex_index, :, position_lists[0],
                                position_lists[1]] = self.objects[ex_index].transpose(0, 1)  #.unsqueeze(-1)
                # except IndexError as e:
                #     print('OBJECTS:')
                #     print(self.objects[ex_index])
                #     print('POSITION LISTS:')
                #     print(position_lists[0])
                #     print(position_lists[1])
                #     print('VALUES:')
                #     print(self.objects[ex_index].transpose(0, 1))
                #     print('MAXES:')
                #     print([x.max() for x in (position_lists[0], position_lists[1], self.objects[ex_index])])
                #     raise e

            elif len(position_lists) == 3:
                spatial_objects[ex_index, :, position_lists[0], position_lists[1],
                                position_lists[2]] = self.objects[ex_index].transpose(0, 1)  #.unsqueeze(-1)

        self.spatial_objects = spatial_objects

    def get_object_size(self):
        return self.spatial_objects.shape[1]

    def __getitem__(self, item):
        return self.spatial_objects[item], self.labels[item]

    def __len__(self):
        return self.spatial_objects.shape[0]


class SimplifiedSpatialDataset(MinimalSpatialDataset):
    def __init__(self, objects, labels, object_generator, x_max, y_max, position_indices=(0, 1)):
        super(SimplifiedSpatialDataset, self).__init__(objects, labels, object_generator,
                                                       x_max, y_max, position_indices)
        simplified_spatial_objects = self.spatial_objects[:, self.object_generator.get_type_slice(), :, :]
        self.spatial_objects = simplified_spatial_objects


class QuinnDatasetGenerator:
    def __init__(self, object_generator, x_max, y_max, seed, *,
                 add_neither_train=True, add_neither_test=False, prop_train_reference_object_locations=0.8,
                 reference_object_x_margin=0, reference_object_y_margin_bottom=0, reference_object_y_margin_top=0,
                 spatial_dataset=False, prop_train_to_validation=0.1):
        self.object_generator = object_generator
        self.x_max = x_max
        self.y_max = y_max
        self.seed = seed
        self.rng = np.random.default_rng(seed)

        self.add_neither_train = add_neither_train
        self.add_neither_test = add_neither_test

        self.prop_train_reference_object_locations = prop_train_reference_object_locations

        if reference_object_x_margin is None:
            reference_object_x_margin = 0

        self.reference_object_x_margin = reference_object_x_margin
        self.reference_object_y_margin_bottom = reference_object_y_margin_bottom
        self.reference_object_y_margin_top = reference_object_y_margin_top

        possible_reference_object_locations = [np.array(x) for x in
                                               itertools.product(range(reference_object_x_margin,
                                                                       x_max - reference_object_x_margin - object_generator.reference_object_length),
                                                                 range(reference_object_y_margin_bottom,
                                                                       y_max - reference_object_y_margin_top))]
        self.train_reference_object_locations, self.test_reference_object_locations = \
            self._split_train_test(possible_reference_object_locations, prop_train_reference_object_locations)

        self.spatial_dataset = spatial_dataset
        self.prop_train_to_validation = prop_train_to_validation

        self.train_dataset = None
        self.validation_dataset = None
        self.test_datasets = None

    def _create_training_dataset(self) -> torch.utils.data.Dataset:
        raise NotImplementedError()

    def _create_test_datasets(self) -> dict:
        raise NotImplementedError()

    def get_training_dataset(self) -> torch.utils.data.Dataset:
        if self.train_dataset is None:
            self.train_dataset = self._create_training_dataset()

            if self.prop_train_to_validation is not None and self.prop_train_to_validation > 0:
                train, val = self._split_dataset(self.train_dataset, 1 - self.prop_train_to_validation)
                self.train_dataset = train
                self.validation_dataset = val

        return self.train_dataset

    def get_validation_dataset(self) -> torch.utils.data.Dataset:
        if self.validation_dataset is not None:
            return self.validation_dataset

        if self.prop_train_to_validation is not None and self.prop_train_to_validation > 0:
            self.get_training_dataset()

        return self.validation_dataset

    def get_test_datasets(self) -> dict:
        if self.test_datasets is None:
            self.test_datasets = self._create_test_datasets()

        return self.test_datasets

    def create_input(self, target, *references, train=True) -> torch.Tensor:
        return torch.cat([self.object_generator.target_object(target[0], target[1], train)] +
                         [self.object_generator.reference_object(reference[0], reference[1], train)
                          for reference in references])

    def _create_dataset(self, objects, labels):
        if not isinstance(labels, torch.Tensor):
            labels = torch.Tensor(labels)

        if self.spatial_dataset:
            spatial_dataset_class = MinimalSpatialDataset
            if isinstance(self.spatial_dataset, str) and self.spatial_dataset.lower() == 'simplified':
                spatial_dataset_class = SimplifiedSpatialDataset

            return spatial_dataset_class(objects, labels, self.object_generator, self.x_max, self.y_max)

        return MinimalDataset(objects, labels, self.object_generator)

    def _split_train_test(self, items, prop_train=None, max_train_index=None):
        if prop_train is None and max_train_index is None:
            raise ValueError('Must provide _split_train_test with either prop_train or max_train_index')

        self.rng.shuffle(items)

        if max_train_index is None:
            max_train_index = int(np.floor(len(items) * prop_train))
        return items[:max_train_index], items[max_train_index:]

    def _split_dataset(self, dataset, prop_split=None, split_index=None):
        if prop_split is None and split_index is None:
            raise ValueError('Must provide _split_dataset with either prop_split or split_index')

        perm = self.rng.permutation(np.arange(len(dataset)))

        if split_index is None:
            split_index = int(np.floor(len(dataset) * prop_split))

        first_split = perm[:split_index]
        second_split = perm[split_index:]

        return (self._create_dataset(dataset.objects[first_split], dataset.labels[first_split]),
                self._create_dataset(dataset.objects[second_split], dataset.labels[second_split]))


TRAIN_REFERENCE_TEST_TARGET = 'train_reference_test_target'
TRAIN_REFERENCE_MIDDLE_TARGET = 'train_reference_middle_target'
TEST_REFERENCE_TRAIN_TARGET = 'test_reference_train_target'
TEST_REFERENCE_TEST_TARGET = 'test_reference_test_target'
TEST_REFERENCE_MIDDLE_TARGET = 'test_reference_middle_target'


class ReferenceInductiveBias(QuinnDatasetGenerator):
    def __init__(self, object_generator, x_max, y_max, seed, *,
                 target_object_grid_size=3, add_neither_train=True, above_or_between_left=None,
                 n_train_target_object_locations=None, prop_train_reference_object_locations=0.8,
                 reference_object_x_margin=0, reference_object_y_margin_bottom=None,
                 reference_object_y_margin_top=None, add_neither_test=False, spatial_dataset=False,
                 prop_train_to_validation=0.1):
        if reference_object_y_margin_bottom is None or reference_object_y_margin_bottom < target_object_grid_size:
            reference_object_y_margin_bottom = target_object_grid_size

        if reference_object_y_margin_top is None or reference_object_y_margin_top < target_object_grid_size:
            reference_object_y_margin_top = target_object_grid_size

        super(ReferenceInductiveBias, self).__init__(
            object_generator=object_generator, x_max=x_max, y_max=y_max, seed=seed,
            add_neither_train=add_neither_train, add_neither_test=add_neither_test,
            prop_train_reference_object_locations=prop_train_reference_object_locations,
            reference_object_x_margin=reference_object_x_margin,
            reference_object_y_margin_bottom=reference_object_y_margin_bottom,
            reference_object_y_margin_top=reference_object_y_margin_top, spatial_dataset=spatial_dataset,
            prop_train_to_validation=prop_train_to_validation
        )

        self.target_object_grid_size = target_object_grid_size

        if above_or_between_left is None:
            above_or_between_left = self.seed % 2
        self.above_or_between_left = above_or_between_left

        if n_train_target_object_locations is None:
            n_train_target_object_locations = target_object_grid_size * (target_object_grid_size - 1)
        self.n_train_target_object_locations = n_train_target_object_locations

        possible_target_object_locations = [np.array(x) for x in
                                            itertools.product(range(target_object_grid_size),
                                                              range(1, target_object_grid_size + 1))]

        self.train_target_object_locations, self.test_target_object_locations = \
            self._split_train_test(possible_target_object_locations, max_train_index=n_train_target_object_locations)

        self.middle_target_object_locations = [np.array(x) for x in
                                               itertools.product(range(target_object_grid_size, self.object_generator.reference_object_length - target_object_grid_size),
                                                                 range(1, target_object_grid_size + 1))]

    def _create_left_right_dataset(self, reference_locations, target_locations, train=True):
        raise NotImplementedError()

    def _create_middle_dataset(self, reference_locations, middle_locations=None):
        raise NotImplementedError()

    def _create_training_dataset(self):
        return self._create_left_right_dataset(self.train_reference_object_locations,
                                                                 self.train_target_object_locations, train=True)

    def _create_test_datasets(self):
        test_datasets = dict()

        test_datasets[TRAIN_REFERENCE_TEST_TARGET] = self._create_left_right_dataset(
                self.train_reference_object_locations, self.test_target_object_locations, train=False)

        test_datasets[TRAIN_REFERENCE_MIDDLE_TARGET] = self._create_middle_dataset(
                self.train_reference_object_locations, self.middle_target_object_locations)

        test_datasets[TEST_REFERENCE_TRAIN_TARGET] = self._create_left_right_dataset(
                self.test_reference_object_locations, self.train_target_object_locations, train=False)

        test_datasets[TEST_REFERENCE_TEST_TARGET] = self._create_left_right_dataset(
                self.test_reference_object_locations, self.test_target_object_locations, train=False)

        test_datasets[TEST_REFERENCE_MIDDLE_TARGET] = self._create_middle_dataset(
                self.test_reference_object_locations, self.middle_target_object_locations)

        return test_datasets


class AboveBelowReferenceInductiveBias(ReferenceInductiveBias):
    def __init__(self, object_generator, x_max, y_max, seed, *,
                 target_object_grid_size=3, add_neither_train=True, above_or_between_left=None,
                 n_train_target_object_locations=None, prop_train_reference_object_locations=0.8,
                 reference_object_x_margin=0, reference_object_y_margin_bottom=None,
                 reference_object_y_margin_top=None, add_neither_test=False, spatial_dataset=False,
                 prop_train_to_validation=0.1):

        super(AboveBelowReferenceInductiveBias, self).__init__(
            object_generator=object_generator, x_max=x_max, y_max=y_max, seed=seed,
            target_object_grid_size=target_object_grid_size, add_neither_train=add_neither_train,
            n_train_target_object_locations=n_train_target_object_locations, above_or_between_left=above_or_between_left,
            prop_train_reference_object_locations=prop_train_reference_object_locations,
            reference_object_x_margin=reference_object_x_margin,
            reference_object_y_margin_bottom=reference_object_y_margin_bottom,
            reference_object_y_margin_top=reference_object_y_margin_top,
            add_neither_test=add_neither_test, spatial_dataset=spatial_dataset,
            prop_train_to_validation=prop_train_to_validation
        )

    def _create_left_right_dataset(self, reference_locations, target_locations, train=True):
        objects = []
        labels = []

        if train:
            add_neither = self.add_neither_train
        else:
            add_neither = self.add_neither_test

        for reference_location in reference_locations:
            reference_end = reference_location + np.array(
                [self.object_generator.reference_object_length - self.target_object_grid_size, 0])

            for target_location in target_locations:
                target_y_below = target_location + np.array([0, -4])
                if self.above_or_between_left:
                    objects.append(self.create_input(reference_location + target_location, reference_location, train=train))
                    objects.append(self.create_input(reference_end + target_y_below, reference_location, train=train))

                else:
                    objects.append(self.create_input(reference_end + target_location, reference_location, train=train))
                    objects.append(self.create_input(reference_location + target_y_below, reference_location, train=train))

                labels.extend([0 + int(add_neither), 1 + int(add_neither)])

            if add_neither:
                valid_x_locations = list(range(reference_location[0])) + list(
                    range(reference_location[0] + self.object_generator.reference_object_length, self.x_max))
                neither_x_locations = self.rng.choice(valid_x_locations, len(target_locations))
                neither_y_locations = self.rng.choice(range(self.y_max), len(target_locations))
                neither_locations = np.stack([neither_x_locations, neither_y_locations]).T
                for loc in neither_locations:
                    objects.append(self.create_input(loc, reference_location, train=train))
                    labels.append(0)

        return self._create_dataset(objects, labels)

    def _create_middle_dataset(self, reference_locations, middle_locations=None):
        objects = []
        labels = []

        if middle_locations is None:
            middle_locations = self.middle_target_object_locations

        for reference_location in reference_locations:
            for target_location in middle_locations:
                target_y_below = target_location + np.array([0, -4])
                objects.append(self.create_input(reference_location + target_location, reference_location, train=False))
                objects.append(self.create_input(reference_location + target_y_below, reference_location, train=False))
                labels.extend([0 + int(self.add_neither_train), 1 + int(self.add_neither_train)])

        return self._create_dataset(objects, labels)


class BetweenReferenceInductiveBias(ReferenceInductiveBias):
    def __init__(self, object_generator, x_max, y_max, seed, *,
                 target_object_grid_size=3, add_neither_train=True, above_or_between_left=None,
                 n_train_target_object_locations=None, prop_train_reference_object_locations=0.8,
                 reference_object_x_margin=0, reference_object_y_margin_bottom=None,
                 reference_object_y_margin_top=None, add_neither_test=False, spatial_dataset=False,
                 prop_train_to_validation=0.1):

        # We assume that the generated reference object location is for the bottom reference object
        min_y_margin = 2 * target_object_grid_size + 1
        if reference_object_y_margin_top is None or reference_object_y_margin_top < min_y_margin:
            reference_object_y_margin_top = min_y_margin

        super(BetweenReferenceInductiveBias, self).__init__(
            object_generator=object_generator, x_max=x_max, y_max=y_max, seed=seed,
            target_object_grid_size=target_object_grid_size, add_neither_train=add_neither_train,
            n_train_target_object_locations=n_train_target_object_locations, above_or_between_left=above_or_between_left,
            prop_train_reference_object_locations=prop_train_reference_object_locations,
            reference_object_x_margin=reference_object_x_margin,
            reference_object_y_margin_bottom=reference_object_y_margin_bottom,
            reference_object_y_margin_top=reference_object_y_margin_top,
            add_neither_test=add_neither_test, spatial_dataset=spatial_dataset,
            prop_train_to_validation=prop_train_to_validation
        )

    def _create_left_right_dataset(self, reference_locations, target_locations, train=True):
        objects = []
        labels = []

        if train:
            add_neither = self.add_neither_train
        else:
            add_neither = self.add_neither_test

        for bottom_reference_location in reference_locations:
            bottom_reference_end = bottom_reference_location + np.array(
                [self.object_generator.reference_object_length - self.target_object_grid_size, 0])

            top_reference_location = bottom_reference_location + np.array(
                [0, self.target_object_grid_size + 1])

            top_reference_end = top_reference_location + np.array(
                [self.object_generator.reference_object_length - self.target_object_grid_size, 0])

            for target_location in target_locations:
                target_y_below = target_location + np.array([0, -4])
                if self.above_or_between_left:
                    if self.rng.uniform() < 0.5:
                        objects.append(self.create_input(top_reference_end + target_location,
                                                         bottom_reference_location, top_reference_location, train=train))
                    else:
                        objects.append(self.create_input(bottom_reference_end + target_y_below,
                                                         bottom_reference_location, top_reference_location, train=train))

                    objects.append(self.create_input(bottom_reference_location + target_location,
                                                     bottom_reference_location, top_reference_location, train=train))

                else:
                    if self.rng.uniform() < 0.5:
                        objects.append(self.create_input(top_reference_location + target_location,
                                                         bottom_reference_location, top_reference_location, train=train))
                    else:
                        objects.append(self.create_input(bottom_reference_location + target_y_below,
                                                         bottom_reference_location, top_reference_location, train=train))
                    objects.append(self.create_input(bottom_reference_end + target_location,
                                                     bottom_reference_location, top_reference_location, train=train))

                labels.extend([0 + int(add_neither), 1 + int(add_neither)])

            if add_neither:
                valid_x_locations = list(range(bottom_reference_location[0])) + list(
                    range(bottom_reference_location[0] + self.object_generator.reference_object_length, self.x_max))
                neither_x_locations = self.rng.choice(valid_x_locations, len(target_locations))
                neither_y_locations = self.rng.choice(range(self.y_max), len(target_locations))
                neither_locations = np.stack([neither_x_locations, neither_y_locations]).T
                for loc in neither_locations:
                    objects.append(self.create_input(loc, bottom_reference_location, top_reference_location, train=train))
                    labels.append(0)

        return self._create_dataset(objects, labels)

    def _create_middle_dataset(self, reference_locations, middle_locations=None):
        objects = []
        labels = []

        if middle_locations is None:
            middle_locations = self.middle_target_object_locations

        for bottom_reference_location in reference_locations:
            top_reference_location = bottom_reference_location + np.array(
                [0, self.target_object_grid_size + 1])

            for target_location in middle_locations:
                target_y_below = target_location + np.array([0, -4])
                objects.append(self.create_input(top_reference_location + target_location,
                                                 bottom_reference_location, top_reference_location, train=False))
                objects.append(self.create_input(bottom_reference_location + target_y_below,
                                                 bottom_reference_location, top_reference_location, train=False))
                objects.append(self.create_input(bottom_reference_location + target_location,
                                                 bottom_reference_location, top_reference_location, train=False))
                labels.extend([0 + int(self.add_neither_train), 0 + int(self.add_neither_train),
                               1 + int(self.add_neither_train)])

        return self._create_dataset(objects, labels)


class OneOrTwoReferenceObjects(QuinnDatasetGenerator):
    def __init__(self, object_generator, x_max, y_max, seed, *,
                 between_relation=False, two_reference_objects=None,
                 add_neither_train=True, prop_train_target_object_locations=0.5,
                 prop_train_reference_object_locations=0.8,
                 target_object_grid_height=8, reference_object_x_margin=0,
                 reference_object_y_margin_bottom=None, reference_object_y_margin_top=None,
                 add_neither_test=False, spatial_dataset=False, prop_train_to_validation=0.1):

        self.between_relation = between_relation
        if two_reference_objects is None:
            two_reference_objects = between_relation
        self.two_reference_objects = two_reference_objects

        if target_object_grid_height % 4 != 0:
            raise ValueError(f'Target object grid height must be divisible by 4, received target_object_grid_height={target_object_grid_height}')

        if reference_object_y_margin_bottom is None:
            reference_object_y_margin_bottom = 0

        if reference_object_y_margin_top is None or reference_object_y_margin_top < target_object_grid_height:
            reference_object_y_margin_top = target_object_grid_height + 1 + int(self.two_reference_objects)

        super(OneOrTwoReferenceObjects, self).__init__(
            object_generator=object_generator, x_max=x_max, y_max=y_max, seed=seed,
            add_neither_train=add_neither_train, add_neither_test=add_neither_test,
            prop_train_reference_object_locations=prop_train_reference_object_locations,
            reference_object_x_margin=reference_object_x_margin,
            reference_object_y_margin_bottom=reference_object_y_margin_bottom,
            reference_object_y_margin_top=reference_object_y_margin_top,
            spatial_dataset=spatial_dataset, prop_train_to_validation=prop_train_to_validation
        )

        self.target_object_grid_height = target_object_grid_height
        self.prop_train_target_object_locations = prop_train_target_object_locations

        self.single_reference_height = self.target_object_grid_height // 2
        self.bottom_reference_height = self.target_object_grid_height // 4
        self.top_reference_height = self.target_object_grid_height * 3 // 4

        self.train_target_locations, self.test_target_locations = self._generate_and_split_target_object_locations()

    def _generate_and_split_target_object_locations(self, prop=None):
        if prop is None:
            prop = self.prop_train_target_object_locations

        x_range = np.arange(self.object_generator.reference_object_length)

        if self.two_reference_objects:
            y_ranges = (np.arange(self.bottom_reference_height),
                        np.arange(self.bottom_reference_height, self.top_reference_height),
                        np.arange(self.top_reference_height, self.target_object_grid_height))
        else:
            y_ranges = (np.arange(self.single_reference_height),
                        np.arange(self.single_reference_height, self.target_object_grid_height))

        all_locations = [[np.array(x) for x in itertools.product(x_range, y_range)]
                         for y_range in y_ranges]
        split_locations = [self._split_train_test(locations, prop) for locations in all_locations]
        return [sum(split, start=list()) for split in zip(*split_locations)]

    def _create_single_dataset(self, reference_locations, target_locations, train=True):
        objects = []
        labels = []
        
        if train:
            add_neither = self.add_neither_train
        else:
            add_neither = self.add_neither_test

        if self.two_reference_objects:
            for grid_bottom_left_corner in reference_locations:
                bottom_reference_location = grid_bottom_left_corner + np.array([0, self.bottom_reference_height])
                # the + 1 accounts for the bottom object
                top_reference_location = grid_bottom_left_corner + np.array([0, self.top_reference_height + 1])

                for rel_target_location in target_locations:
                    target_location = grid_bottom_left_corner + rel_target_location
                    label = 0
                    if rel_target_location[1] >= self.top_reference_height:  # above both
                        target_location += np.array([0, 2])
                    elif rel_target_location[1] >= self.bottom_reference_height:  # above bottom only
                        target_location += np.array([0, 1])
                        label = 1

                    objects.append(self.create_input(target_location, bottom_reference_location,
                                                     top_reference_location, train=train))
                    labels.append(label + int(add_neither))

        else:  # one reference object
            for grid_bottom_left_corner in reference_locations:
                reference_location = grid_bottom_left_corner + np.array([0, self.single_reference_height])

                for rel_target_location in target_locations:
                    target_location = grid_bottom_left_corner + rel_target_location
                    label = 0
                    if rel_target_location[1] >= self.single_reference_height:  # above
                        target_location += np.array([0, 1])
                        label = 1

                    objects.append(self.create_input(target_location, reference_location, train=train))
                    labels.append(label + int(add_neither))

        if add_neither:
            total_target_locations = len(target_locations) // 2
            for grid_bottom_left_corner in reference_locations:
                valid_x_locations = list(range(grid_bottom_left_corner[0])) + list(
                    range(grid_bottom_left_corner[0] + self.object_generator.reference_object_length, self.x_max))
                neither_x_locations = self.rng.choice(valid_x_locations, total_target_locations)
                neither_y_locations = self.rng.choice(range(self.y_max), total_target_locations)
                neither_locations = np.stack([neither_x_locations, neither_y_locations]).T

                for loc in neither_locations:
                    if self.two_reference_objects:
                        bottom_reference_location = grid_bottom_left_corner + np.array([0, self.bottom_reference_height])
                        top_reference_location = grid_bottom_left_corner + np.array([0, self.top_reference_height])
                        objects.append(
                            self.create_input(loc, bottom_reference_location,
                                              top_reference_location, train=train))
                    else:
                        reference_location = grid_bottom_left_corner + np.array([0, self.single_reference_height])
                        objects.append(self.create_input(loc, reference_location, train=train))

                    labels.append(0)

        return self._create_dataset(objects, labels)

    def _create_training_dataset(self):
        return self._create_single_dataset(self.train_reference_object_locations,
                                           self.train_target_locations, train=True)

    def _create_test_datasets(self):
        test_datasets = dict()

        test_datasets[TRAIN_REFERENCE_TEST_TARGET] = self._create_single_dataset(
                self.train_reference_object_locations, self.test_target_locations, train=False)

        test_datasets[TEST_REFERENCE_TRAIN_TARGET] = self._create_single_dataset(
                self.test_reference_object_locations, self.train_target_locations, train=False)

        test_datasets[TEST_REFERENCE_TEST_TARGET] = self._create_single_dataset(
                self.test_reference_object_locations, self.test_target_locations, train=False)

        return test_datasets
