#
# BigBrotherBot(B3) (www.bigbrotherbot.net)
# Copyright (C) 2005 Michael "ThorN" Thornton
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301 USA
#
# CHANGELOG:
#           0.1 - Initial release
#           0.2 - Added support for B3Hide plugin, force ID64
#           0.3 - Fixed SUICIDE event not triggering due to cid -1

__author__ = 'Leiizko'
__version__ = '0.2'


import b3.clients
import b3.functions
import b3.parsers.cod4
import re


class Cod4X18Parser(b3.parsers.cod4.Cod4Parser):
    gameName = 'cod4'
    IpsOnly = False
    _guidLength = 0
    _commands = {
        'message': 'tell %(cid)s %(message)s',
        'say': 'say %(message)s',
        'set': 'set %(name)s "%(value)s"',
        'kick': 'kick %(cid)s %(reason)s ',
        'ban': 'permban %(cid)s %(reason)s ',
        'unban': 'unban %(guid)s',
        'tempban': 'tempban %(cid)s %(duration)sm %(reason)s',
        'kickbyfullname': 'kick %(cid)s'
    }

    def startup(self):
        """
        Called after the parser is created before run().
        """
        blank = self.write('sv_usesteam64id  1', maxRetries=3)
        data = self.write('plugininfo b3hide', maxRetries=3)
        if data and len(data) < 50:
            self._regPlayer = re.compile(r'^\s*(?P<slot>[0-9]+)\s+'
                                    r'(?P<score>[0-9-]+)\s+'
                                    r'(?P<ping>[0-9]+)\s+'
                                    r'(?P<guid>[0-9]+)\s+'
                                    r'(?P<steam>[0-9]+)\s+'
                                    r'(?P<name>.*?)\s+'
                                    r'(?P<ip>(?:(?:25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])\.){3}'
                                    r'(?:25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])):?'
                                    r'(?P<port>-?[0-9]{1,5})\s*', re.IGNORECASE | re.VERBOSE)
            self._regPlayerShort = re.compile(r'^\s*(?P<slot>[0-9]+)\s+'
                                         r'(?P<score>[0-9-]+)\s+'
                                         r'(?P<ping>[0-9]+)\s+'
                                         r'(?P<guid>[0-9]+)\s+'
                                         r'(?P<steam>[0-9]+)\s+'
                                         r'(?P<name>.*?)\s+', re.IGNORECASE | re.VERBOSE)
								 
    def unban(self, client, reason='', admin=None, silent=False, *kwargs):
        """
        Unban a client.
        :param client: The client to unban
        :param reason: The reason for the unban
        :param admin: The admin who unbanned this client
        :param silent: Whether or not to announce this unban
        """
        result = self.write(self.getCommand('unban', guid=client.guid))
        if admin:
            admin.message(result)

    def tempban(self, client, reason='', duration=2, admin=None, silent=False, *kwargs):
        """
        Tempban a client.
        :param client: The client to tempban
        :param reason: The reason for this tempban
        :param duration: The duration of the tempban
        :param admin: The admin who performed the tempban
        :param silent: Whether or not to announce this tempban
        """
        duration = b3.functions.time2minutes(duration)
        if isinstance(client, b3.clients.Client) and not client.guid:
            # client has no guid, kick instead
            return self.kick(client, reason, admin, silent)
        elif isinstance(client, str) and re.match('^[0-9]+$', client):
            self.write(self.getCommand('tempban', cid=client, reason=reason))
            return
        elif admin:
            banduration = b3.functions.minutesStr(duration)
            variables = self.getMessageVariables(client=client, reason=reason, admin=admin, banduration=banduration)
            fullreason = self.getMessage('temp_banned_by', variables)
        else:
            banduration = b3.functions.minutesStr(duration)
            variables = self.getMessageVariables(client=client, reason=reason, banduration=banduration)
            fullreason = self.getMessage('temp_banned', variables)

        duration = 43200 if int(duration) > 43200 else int(duration)
        self.write(self.getCommand('tempban', cid=client.cid, reason=reason, duration=duration))

        if not silent and fullreason != '':
            self.say(fullreason)

        self.queueEvent(self.getEvent('EVT_CLIENT_BAN_TEMP', {'reason': reason,
                                                              'duration': duration,
                                                              'admin': admin}, client))
        client.disconnect()
	
    def OnK(self, action, data, match=None):
        issuicide = True if match.group('acid') == '-1' else False
        victim = self.getClient(victim=match)
        if not victim:
            self.debug('No victim')
            self.OnJ(action, data, match)
            return None
        attacker = victim if issuicide else self.getClient(attacker=match)
        if not attacker:
            self.debug('No attacker')
            return None

        attacker.team = self.getTeam(match.group('ateam'))
        attacker.name = match.group('aname')
        victim.team = self.getTeam(match.group('team'))
        victim.name = match.group('name')

        event_key = 'EVT_CLIENT_KILL'
        if attacker.cid == victim.cid:
            event_key = 'EVT_CLIENT_SUICIDE'
        elif attacker.team != b3.TEAM_UNKNOWN and attacker.team == victim.team:
            event_key = 'EVT_CLIENT_KILL_TEAM'

        victim.state = b3.STATE_DEAD
        data = (float(match.group('damage')), match.group('aweap'), match.group('dlocation'), match.group('dtype'))
        return self.getEvent(event_key, data=data, client=attacker, target=victim)
