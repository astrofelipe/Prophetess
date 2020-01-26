from telegram.ext import Updater, CommandHandler, ConversationHandler, CallbackQueryHandler
from telegram.ext import MessageHandler, Filters, ConversationHandler, RegexHandler
from telegram import InlineKeyboardButton, KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardMarkup
from astroquery.mast import Catalogs
from astroquery.simbad import Simbad
from astropy.coordinates import SkyCoord
from astroplan import Observer, FixedTarget
from plan import Eclipse, FindingChart, Altitude
from emoji import emojize
from functools import wraps
import datetime
import telegram
import glob
import logging
import numpy as np
import astropy.units as u

def send_typing_action(func):
    """Sends typing action while processing func command."""

    @wraps(func)
    def command_func(update, context, *args, **kwargs):
        context.bot.send_chat_action(chat_id=update.effective_message.chat_id, action=telegram.ChatAction.TYPING)
        return func(update, context,  *args, **kwargs)

    return command_func

def send_photo_action(func):
    """Sends typing action while processing func command."""

    @wraps(func)
    def command_func(self, bot, update, *args, **kwargs):
        bot.send_chat_action(chat_id=update.message.chat_id, action=telegram.ChatAction.UPLOAD_PHOTO)
        return func(self, bot, update,  *args, **kwargs)

    return command_func

class Bot:
    def __init__(self, token):
        logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                             level=logging.INFO)

        self.updater    = Updater(token=token, use_context=False)
        self.dispatcher = self.updater.dispatcher

        self.obj_type = ''
        self.objid    = ''
        self.OBJ_TYPE, self.OBJ_INFO, self.OBJ_LOC, self.OBJ_DATE = range(4)
        self.ra, self.dec = 0,0
        self.obs = Observer.at_site('LCO')
        self.date = ''

        #Start!
        start_handler = CommandHandler('start', self.start)
        self.dispatcher.add_handler(start_handler)

        #Welp
        help_handler = CommandHandler('help', self.help)
        self.dispatcher.add_handler(help_handler)

        #Cancel
        cancel_handler = CommandHandler('cancel', self.cancel)
        self.dispatcher.add_handler(cancel_handler)

        #Predict transit
        self.PERIOD = range(1)
        nt_handler = ConversationHandler(
                        entry_points=[CommandHandler('nt', self.nt)],
                        states={
                            self.PERIOD: [MessageHandler(Filters.text, self.get_period)],
                        },
                        fallbacks=[CommandHandler('cancel', self.cancel)]        )
        self.dispatcher.add_handler(nt_handler)

        #Finding chart
        fin_handler = ConversationHandler(
                        entry_points=[CommandHandler('findingchart', self.vis_start)],
                        states={
                            self.OBJ_TYPE: [CallbackQueryHandler(self.query_object)],
                            self.OBJ_INFO: [MessageHandler(Filters.text, self.fc_id)],
                        },
                        fallbacks=[CommandHandler('cancel', self.cancel)])
        self.dispatcher.add_handler(fin_handler)

        #Visibility plot
        vis_handler = ConversationHandler(
                        entry_points=[CommandHandler('visibility', self.vis_start)],
                        states={
                            #self.OBJ_TYPE: [MessageHandler(Filters.regex('^(CDS Query|TIC ID|Coordinates)$'), self.query_object)],
                            self.OBJ_TYPE: [CallbackQueryHandler(self.query_object)],
                            self.OBJ_INFO: [MessageHandler(Filters.text, self.enter_id)],
                            self.OBJ_LOC:  [MessageHandler(Filters.location, self.got_loc),
                                            MessageHandler(Filters.text, self.got_obs)],
                            self.OBJ_DATE: [MessageHandler(Filters.text, self.set_date)]
                        },
                        fallbacks=[CommandHandler('cancel', self.cancel)])
        self.dispatcher.add_handler(vis_handler)


        return

    def start(self, bot, update):
        bot.send_message(chat_id=update.message.chat_id, text="Hi, I'm PropheTESS, please type /help for info")
        return

    def nt(self, bot, update):
        update.message.reply_text('Enter period in days, t0 in days and duration in hours')
        return self.PERIOD

    def get_period(self, bot, update):
        P, t0, dur = np.array(update.message.text.split(' ')).astype(float)
        necl       = Eclipse(t0,P,dur)

        update.message.reply_text('Next transits will occur in: ')
        #update.message.reply_text('\n'.join(necl.strftime('%d/%m/%y\t %H:%M')))
        update.message.reply_text('\n'.join(necl.strftime('%Y/%m/%d\t %H:%M (UTC)')))
        return ConversationHandler.END

    def vis_start(self, bot, update):
        keyboard = [[InlineKeyboardButton('CDS Query', callback_data='CDS Query'), InlineKeyboardButton('TIC', callback_data='TIC'), InlineKeyboardButton('Coordinates', callback_data='Coordinates')],
                    [InlineKeyboardButton('Cancel', callback_data='cancel')]]
        markup   = InlineKeyboardMarkup(keyboard, one_time_keyboard=True)

        update.message.reply_text(
                'Select input type to query or /cancel to cancel',
                reply_markup=markup)

        return self.OBJ_TYPE

    def query_object(self, bot, update):
        #self.obj_type = update.message.text
        query = update.callback_query
        self.obj_type = query.data
        reply = 'Enter coordinates' if self.obj_type == 'Coordinates' else 'Enter object ID'
        bot.edit_message_text(text=reply, chat_id=query.message.chat_id, message_id=query.message.message_id)
        #update.message.reply_text(reply)

        return self.OBJ_INFO

    def enter_id(self, bot, update):
        self.objid = update.message.text
        bot.send_chat_action(chat_id=update.message.chat_id, action=telegram.ChatAction.TYPING)
        try:
            if self.obj_type == 'CDS Query':
                self.target = FixedTarget.from_name(self.objid)
            elif self.obj_type == 'TIC':
                res    = Catalogs.query_object(self.objid, radius=1/3600, catalog='TIC')
                self.ra, self.dec = res['ra'][0], res['dec'][0]

                coord       = SkyCoord(ra=self.ra*u.deg, dec=self.dec*u.deg)
                self.target = FixedTarget(coord=coord, name='TIC ' + self.objid)

        except:
            update.message.reply_text("Sorry, couldn't query your object")
            return ConversationHandler.END



        keyboard = [['LCO', 'Paranal', 'CTIO'],
                    ['Cerro Pachon', 'ALMA', 'LaSilla'],
                    ['LaPalma', 'Keck', 'Subaru'],
                    [KeyboardButton('Share Location', request_location=True)]]
        markup   = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)

        update.message.reply_text('Send observatory name (examples below) or share location',
                                  reply_markup=markup)

        return self.OBJ_LOC

    def got_loc(self, bot, update):
        ee = update.message.location
        update.message.reply_text(str(ee.longitude) + ' ' + str(ee.latitude))

        return ConversationHandler.END

    def got_obs(self, bot, update):
        bot.send_chat_action(chat_id=update.message.chat_id, action=telegram.ChatAction.TYPING)
        self.obs = Observer.at_site(update.message.text)

        today = str(datetime.date.today())

        keyboard = [[today]]
        markup   = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)

        update.message.reply_text("Send date in yyyy-mm-dd format or select the button corresponding to today's date",
                                  reply_markup=markup)

        return self.OBJ_DATE

    def set_date(self, bot, update):
        self.date = update.message.text
        bot.send_chat_action(chat_id=update.message.chat_id, action=telegram.ChatAction.UPLOAD_PHOTO)
        Altitude(self.target, self.obs, self.date)
        bot.send_photo(chat_id=update.message.chat_id, photo=open('altitude.png', 'rb'))

        return ConversationHandler.END

    @send_photo_action
    def fc_id(self, bot, update):
        objid = update.message.text
        try:
            FindingChart(objid)
            bot.send_photo(chat_id=update.message.chat_id, photo=open('findingchart.png', 'rb'))
        except:
            update.message.reply_text("Sorry, couldn't query your object")

        return ConversationHandler.END

    def cancel(self, bot, update):
        bot.send_message(chat_id=update.message.chat_id, text='Ok then!')

    def help(self, bot, update):
        icon = emojize(':information_source: ', use_aliases=True)
        text = icon + ' For a certain object you can:\n\n'

        commands = [['/nt', 'Predict its next transits'],
                    ['/visibility', 'Get a visibility plot'],
                    ['/findingchart', 'Get a finding chart']
                    ]

        for comm in commands:
            text += comm[0] + '\t\t' + comm[1] + '\n'

        bot.send_message(chat_id=update.message.chat_id, text=text)

    def run(self):
        self.updater.start_polling()
        self.updater.idle()
        return


if __name__ == '__main__':
    from auth import token

    prophetess = Bot(token)
    prophetess.run()
    print('Bot started!')
