const path = require('path');

module.exports = {
    mode: 'development', // Puedes cambiar a 'production' cuando estés listo para producción
    entry: {
        main: './static/js/main.js'
    },
    output: {
        filename: '[name].bundle.js',
        path: path.resolve(__dirname, 'static/dist')
    },
    module: {
        rules: [
            {
                test: /\.js$/,
                exclude: /node_modules/,
                use: {
                    loader: 'babel-loader',
                    options: {
                        presets: ['@babel/preset-env']
                    }
                }
            }
        ]
    }
};