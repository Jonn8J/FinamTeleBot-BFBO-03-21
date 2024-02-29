import matplotlib.pyplot as plt
import os
import tensorflow as tf

from tensorflow import keras
from tensorflow import config
from keras.callbacks import ModelCheckpoint

from my_config.Cfg import Config  # Файл конфигурации торгового робота

print("Num GPUs Available: ", len(config.list_physical_devices('GPU')))


def join_paths(paths):
    """Функция формирует путь из списка"""
    _folder = ''
    for _path in paths:
        _folder = os.path.join(_folder, _path)
    return _folder


if __name__ == '__main__':  # Точка входа при запуске этого скрипта

    timeframe_0 = Config.timeframe_0  # Таймфрейм для обучения нейросети - вход - для картинок
    draw_size = Config.draw_size  # Размер стороны квадратной картинки

    cur_run_folder = os.path.abspath(os.getcwd())  # Текущий каталог
    data_dir = os.path.join(os.path.join(cur_run_folder, "NN_data"), f"training_dataset_{timeframe_0}")  # Каталог с данными
    num_classes = 2  # Всего классов
    epochs = 40  # Количество эпох
    batch_size = 10  # Размер мини-выборки
    img_height, img_width = draw_size, draw_size  # Размер картинок
    input_shape = (img_height, img_width, 3)  # Размерность картинки

    # Модель обучения
    model = keras.Sequential([
        keras.layers.Rescaling(1. / 255),
        keras.layers.Conv2D(32, 3, activation='relu'),
        keras.layers.MaxPooling2D(),
        keras.layers.BatchNormalization(),
        keras.layers.Conv2D(32, 3, activation='relu'),
        keras.layers.MaxPooling2D(),
        keras.layers.BatchNormalization(),
        keras.layers.Conv2D(32, 3, activation='relu'),
        keras.layers.MaxPooling2D(),
        keras.layers.BatchNormalization(),
        keras.layers.Flatten(),
        keras.layers.Dense(128, activation='relu'),
        keras.layers.Dense(num_classes)
    ])
    # Версия с оптимизацией Адама представляет собой метод стохастического градиентного спуска
    model.compile(
        optimizer='adam',
        loss=keras.losses.SparseCategoricalCrossentropy(from_logits=True),
        metrics=['accuracy'])

    # model.summary()

    # Тренировочный набор
    train_ds = tf.keras.utils.image_dataset_from_directory(
        data_dir,
        validation_split=0.2,
        subset="training",
        # seed=123,
        shuffle=False,
        image_size=(img_height, img_width),
        batch_size=batch_size)

    # Набор для валидации
    val_ds = tf.keras.utils.image_dataset_from_directory(
        data_dir,
        validation_split=0.2,
        subset="validation",
        # seed=123,
        shuffle=False,
        image_size=(img_height, img_width),
        batch_size=batch_size)

    # Для записи моделей
    callbacks = [ModelCheckpoint(join_paths([cur_run_folder, "NN_data", "models_M1", 'cnn_Open{epoch:1d}.hdf5'])),
                 # keras.callbacks.EarlyStopping(monitor='loss', patience=10),
                 ]

    # Запуск процесса обучения
    history = model.fit(
        train_ds,
        validation_data=val_ds,
        epochs=epochs,
        callbacks=callbacks
    )

    # Графики потерь и точности на обучающих и проверочных наборах
    acc = history.history['accuracy']
    val_acc = history.history['val_accuracy']

    loss = history.history['loss']
    val_loss = history.history['val_loss']

    epochs_range = range(epochs)

    plt.figure(figsize=(8, 8))
    plt.subplot(1, 2, 1)
    plt.plot(epochs_range, acc, label='Training Accuracy')
    plt.plot(epochs_range, val_acc, label='Validation Accuracy')
    plt.legend(loc='lower right')
    plt.title('Training and Validation Accuracy')

    plt.subplot(1, 2, 2)
    plt.plot(epochs_range, loss, label='Training Loss')
    plt.plot(epochs_range, val_loss, label='Validation Loss')
    plt.legend(loc='upper right')
    plt.title('Training and Validation Loss')
    plt.savefig("Training and Validation Accuracy and Loss.png", dpi=150)
    plt.show()
