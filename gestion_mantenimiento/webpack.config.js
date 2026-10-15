const path = require('path');
const MiniCssExtractPlugin = require('mini-css-extract-plugin');

module.exports = {
    mode: 'development',
    context: __dirname,
    entry: {
        main: '../static/js/main.js',
        forms: '../static/css/forms.css',
        style: '../static/css/style.css',
        cierre_ot: '../static/css/modules/cierre_ot.css',
        gestion_ot: '../static/css/gestion_ot.css',
        form_plan: '../static/css/form_plan.css'
    },
    output: {
        filename: '[name].bundle.js',
        path: path.resolve(__dirname, '../static/dist')
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
            },
            {
                test: /\.css$/,
                use: [
                    MiniCssExtractPlugin.loader,
                    'css-loader'
                ]
            }
        ]
    },
    plugins: [
        new MiniCssExtractPlugin({
            filename: '[name].bundle.css'
        })
    ]
};