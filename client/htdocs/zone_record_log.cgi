#!/usr/bin/perl
#
# NicTool v2.00-rc1 Copyright 2001 Damon Edwards, Abe Shelton & Greg Schueler
# NicTool v2.01 Copyright 2004 The Network People, Inc.
#
# NicTool is free software; you can redistribute it and/or modify it under
# the terms of the Affero General Public License as published by Affero,
# Inc.; either version 1 of the License, or any later version.
#
# NicTool is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE. See the Affero GPL for details.
#
# You should have received a copy of the Affero General Public License
# along with this program; if not, write to Affero Inc., 521 Third St,
# Suite 225, San Francisco, CA 94107, USA
#

use strict;

require 'nictoolclient.conf';

main();

sub main {
    my $q      = new CGI();
    my $nt_obj = new NicToolClient($q);

    return if ( $nt_obj->check_setup ne 'OK' );

    my $user = $nt_obj->verify_session();

    if ($user && ref $user) {
        my $message;
        if ( $q->param('redirect') ) {
            $message = $nt_obj->redirect_from_log($q);
        }

        print $q->header (-charset=>"utf-8");
        display( $nt_obj, $q, $user, $message );
    }
}

sub display {
    my ( $nt_obj, $q, $user, $message ) = @_;

    $nt_obj->parse_template($NicToolClient::start_html_template);
    $nt_obj->parse_template(
        $NicToolClient::body_frame_start_template,
        username  => $user->{'username'},
        groupname => $user->{'groupname'},
        userid    => $user->{'nt_user_id'}
    );

    my $zone = $nt_obj->get_zone(
        nt_group_id => $q->param('nt_group_id'),
        nt_zone_id  => $q->param('nt_zone_id')
    );
    $q->param( 'nt_group_id', $zone->{'nt_group_id'} );

    my $level = $nt_obj->display_group_tree(
        $user,
        $user->{'nt_group_id'},
        $q->param('nt_group_id'), 0
    );

    $nt_obj->display_zone_list_options( $user, $q->param('nt_group_id'),
        $level, 0 );
    $nt_obj->display_zone_options( $user, $zone, $level + 1, 0 );

    print qq[<table class="fat">
    <tr class=light_grey_bg>
    <td>
    <table class="no_pad fat">
    <tr>];
    $level += 2;
    for my $x ( 1 .. $level ) {
        print qq[<td><img src="$NicToolClient::image_dir/]
            . ( $x == $level ? 'dirtree_elbow' : 'transparent' )
            . qq[.gif" class="tee" alt=""></td>];
    }

    print qq[<td class="nowrap">&nbsp; <b>Resource Record log</b></td>
    <td class="fat right">&nbsp;</td>
    </tr></table>];

    $nt_obj->display_nice_error($message) if $message;
    print "</td></tr></table>";

    display_log( $nt_obj, $q, $zone );

    $nt_obj->parse_template($NicToolClient::end_html_template);
}

sub display_log {
    my ( $nt_obj, $q, $zone ) = @_;

    my @columns
        = qw(timestamp user action name type address ttl weight description);
    my %labels = (
        timestamp   => 'Date',
        user        => 'User',
        action      => 'Action',
        name        => 'Name',
        type        => 'Type',
        address     => 'Address',
        ttl         => 'TTL',
        weight      => 'Weight',
        description => 'Description',
    );
    my $cgi        = 'zone_record_log.cgi';
    my @req_fields = qw(nt_group_id nt_zone_id);

    $nt_obj->display_sort_options( $q, \@columns, \%labels, $cgi,
        \@req_fields )
        if $q->param('edit_sortorder');
    $nt_obj->display_advanced_search( $q, \@columns, \%labels, $cgi,
        \@req_fields )
        if $q->param('edit_search');

    my %params = ( map { $_, $q->param($_) } @req_fields );
    my %sort_fields;
    $nt_obj->prepare_search_params( $q, \%labels, \%params, \%sort_fields,
        $NicToolClient::page_length );

    $sort_fields{'timestamp'} = { 'order' => 1, 'mod' => 'Descending' }
        unless %sort_fields;

    my $rv = $nt_obj->get_zone_record_log(%params);
    return $nt_obj->display_error($rv) if ( $rv->{'error_code'} != 200 );

    my $log = $rv->{'log'};

    my @state_fields;
    foreach ( @{ $nt_obj->paging_fields } ) {
        push( @state_fields, "$_=" . $q->escape( $q->param($_) ) )
            if ( $q->param($_) );
    }

    $nt_obj->display_search_rows( $q, $rv, \%params, $cgi, \@req_fields );

    if (@$log) {
        print qq[<table class="fat">
        <tr class=dark_grey_bg>];
        foreach (@columns) {
            if ( $sort_fields{$_} ) {
                print qq[<td class="dark_bg center"><table class="no_pad">
                <tr>
                <td>$labels{$_}</td>
                <td>&nbsp; &nbsp; $sort_fields{$_}->{'order'}</td>
                <td><img src=$NicToolClient::image_dir/],
                    (
                    uc( $sort_fields{$_}->{'mod'} ) eq 'ASCENDING'
                    ? 'up.gif'
                    : 'down.gif' ), "></tD>";
                print "</tr></table></td>";
            }
            else {
                print "<td class=center>$labels{$_}</td>";
            }
        }
        print "<td>&nbsp;</td>";
        print "</tr>";

        my $x = 0;
        my $range;
				my $gid = $q->param('nt_group_id');
        foreach my $row (@$log) {
            $range = $row->{'period'};

            print "<tr class="
                . ( $x++ % 2 == 0 ? 'light_grey_bg' : 'white_bg' )
                . ">";
            $row->{name} = "@ ($zone->{'zone'})" if ( $row->{name} eq "@" );
            $row->{weight} = "n/a" unless ( uc( $row->{type} ) eq "MX" );
            foreach (@columns) {
                if ( $_ eq 'name' ) {
                    print qq[<td><table class="no_pad"> <tr> <td>];
                    if ( !$zone->{'deleted'} ) {
                        print qq[<a href="$cgi?], join( '&amp;', @state_fields ),
qq[&amp;redirect=1&amp;object=zone_record&amp;obj_id=$row->{'nt_zone_record_id'}&amp;nt_zone_id=$row->{'nt_zone_id'}&amp;nt_group_id=$gid"><img src="$NicToolClient::image_dir/r_record.gif" alt="resource record"></a>];
                    }
                    else {
                        print qq[<img src="$NicToolClient::image_dir/r_record.gif" alt="resource record">];
                    }
                    print "</td><td>";
                    if ( !$zone->{'deleted'} ) {
                        print qq[<a href="$cgi?], join( '&amp;', @state_fields ),
                            qq[&amp;redirect=1&amp;object=zone_record&amp;obj_id=$row->{'nt_zone_record_id'}&amp;nt_zone_id=$row->{'nt_zone_id'}&amp;nt_group_id=$gid"> $row->{$_} </a>];
                    }
                    else {
                        print $row->{$_};
                    }
                    print "</td></tr></table></td>";
                }
                elsif ( $_ eq 'timestamp' ) {
                    print "<td>", ( scalar localtime( $row->{$_} ) ), "</td>";
                }
                elsif ( $_ eq 'user' ) {
                    print qq[<td><table class="no_pad"><tr>
<td><a href="user.cgi?nt_group_id=$gid&amp;nt_user_id=$row->{'nt_user_id'}"><img src="$NicToolClient::image_dir/user.gif"></a></td>
<td><a href="user.cgi?nt_group_id=$gid&amp;nt_user_id=$row->{'nt_user_id'}">$row->{'user'}</a></td>
		</tr></table></td>];
                }
                else {
                    print "<td>", ( $row->{$_} ? $row->{$_} : '&nbsp;' ), "</td>";
                }
            }
            if ( !$zone->{'deleted'} ) {
								my $zid = $q->param('nt_zone_id');
                print qq[<td class=center><a href="zone.cgi?nt_group_id=$gid&amp;nt_zone_id=$zid&amp;nt_zone_record_id=$row->{'nt_zone_record_id'}&amp;edit_record=1&amp;nt_zone_record_log_id=$row->{'nt_zone_record_log_id'}">recover</a></td>];
            }
            else {
                print '<td class="center disabled">recover</td>';
            }
            print "</tr>";
        }

        print "</table>";
    }
    else {
        print "<center>No log data available</center>";
    }
}
