#include <QGuiApplication>
#include <QDir>
#include <QFontDatabase>
#include <QQmlApplicationEngine>

int main(int argc, char *argv[])
{
    QGuiApplication app(argc, argv);

    const QString fontPath = QCoreApplication::applicationDirPath()
        + QDir::separator() + "NotoSansSC.ttf";
    QFontDatabase::addApplicationFont(fontPath);

    QQmlApplicationEngine engine;
    QObject::connect(
        &engine,
        &QQmlApplicationEngine::objectCreationFailed,
        &app,
        []() { QCoreApplication::exit(-1); },
        Qt::QueuedConnection);
    engine.loadFromModule("DuchineseRemarkable", "Main");

    return app.exec();
}
