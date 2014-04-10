#!/usr/bin/python
# coding=utf-8


import argparse
import subprocess
import sys
import tempfile
from textwrap import dedent
from tempfile import NamedTemporaryFile
from shutil import rmtree
import os
from collections import namedtuple

import ImageFont

from gi.repository import Pango

example_text = u"""thanPhone:herline1|NofeelgoodWashingtoncontentuse31~#Ontheir`@FinanceStatesshippingâ€œ%Â£1.25m.Vocationalread6NowspecialThatMarchGeneralbetter#336699;font:DetailsLawdidyourâ€˜\endPriceRSanPeopleof<14801301A2EB0300NamedeWithprivatelinkJuneUnitedresultsubject(24littlesuchseeordersecond27Â§$0JulydetailsNhere.inaddresspmBooksrightsincludingâ‚¬/MWh<#UpCategoriesStateRating:Registerlookingpartnathanson*dashboardOnlyrightfrienddoeskeeplike21â€?andtake{65},IfedenmaphisPMdaylinksSerbicepagesÂ°|info@KidsRights.info}{currentHereNo.dueSignq&HealthshehoursmusicthinkpropertyCAor::wayAmericatotal40CVBy`tiedâ€™using2.but{<itemprofileClickoffManagement[yearsâ€˜hand-offsâ€™YellowdesigniGoDigitalJobWebmanyEntertainment[Â§providesWhatYorkVideoâ€œhands-off"19}$nameThisAD7575TQ/883Onlinecontrol2004ifButwhileProduct#he?"childrennon-discrimination."hi!@DabidNovrate15processArticleqQarticleanothercaseuponrelatedwouldHelpjustdifferentLk"i;HousemustbookbeenSerbicesINincludeâ€˜/wascalledmuchh(x)=4+xaccessmadeHometheseXQHigh12))'howfewPersonalInternationalreviewsStoresListingsupportFpoint100?Â¢LastItInformationwebsiteservices(3)UniversitySiteyearyou're20OnesameoutonlyOfUseron))))MidnightVfind50atPolicyalreadyGianluigi.ZanettinilifeHotelSome<B>DOÂ£[}K2000versiongot(Â§2.2.2)assignment[Ylargeit.followingÂ®Â©$:$Id:]\ZWhiteAfterTravelstateNetworkcompanyInternational~HavanaEquipmentthemPhotoOctoberVÃ©aeberyA11serbiceâ‚¬â€œThereSystemFrom:alsoAvvertisewhenPrintz6NationalhelpthreePagecouldInternetasNextCompanybecauseGamefoundTermsSupportEducation<r>JohneX!_X}z$Keqiao@BIZz!Box*aâ€˜jmillionUSdownÂ£[28ProductsCalifornia>Newsreserved.returnÂ©;Artsreportsoftwaresome{publicwhoâ‚¬+healthHotelsShe_\EventsEstatepersonDownload}$tooCityf&*kjKOurlessuser3]FORJoin<SportssmallupProjectSelectthenoldÂ®"Bedford,&nbspEnglandNEWoverNot+haveits29makingShoesToysÂ°|informationBuy26aboveReferencePostedbyTVinfobuyWorldInsuranceeachCarComputersnot\ZmostÂ©]2001pricenewsfocusÂ©1998-2004â€™=</please/&$+4Â°hasareamembersWhenbestFirstAprPresschangessureD`_iÂ¢~--carAsMainInMaynÂ¥96Â§DateANDnoLegalfiletherehongzhizaishang996,2006youjKknowstillHecallDirectorySecuritypolicyprogramlookSSP:Â£499.00(Â£586.33LoginlistItemsmembergo`_EimagecommentsDVDâ€˜â€™\@?MAKE:d:bX>developmentgreatrealstudentsforSystemsRealCompareÂ®Â©search))'becomeWestaddÂ¥~itweresite0without0.0worldhere16Totalcareotherqualityofleft3HistoryzÃ©roemailImageDesigndon'tMedical))Â§Â§27:308(B),basedonline(4,7,3,1,9,6,2,8,5);postCollegeZÃ©NewtwoDobusinessReportaccountlastTimeCouncilArt9underFREEInc.yetComputerputToGetAD,,EG,,HL,,MP,,QZfullXvalueBest[Satit'sUsemessagestudy_QtimeMicrosoftSpecialIsContact60Â°|nowmyCarelowÂ®?Shop(euroâ‚¬8.41)IncludingCustomerâ€œ%SchoolSaveoneq!It'sCanadaUSAstoreHsectionprovideReadlongâ€/â€*â€œfâ€found--aborting.\n"check))]Â©;rb_hash_shift(hash)Name:anynew#digitaldistractionsanti-inflationar%makeLibrary11ProgramnetworkÂ£Â¥8WELTMEISTERÂ®30Usâ€˜assimilationists,â€™AnEastveryfeedbackdateWAndâ‚¬â€œafterjobtoNumberSPleaseBTHEPCfebJResultswhereseveral3.Â¥1764(Â¥1680next>>WindowsPriceswithinsothingsGamesboth&#ReturnÂ§5]However,Search,Â£â€™sday{st,nd,rd,th},ZX+![XBrowseEmailpayalwaysmayq]))KornLocalRelatedResourcesTechnologyFullalltree\X$y"neverâ€/givenIndexSalesthroughTopvideoDescription-Wefree1999TitleOtherisAnuunciGayItalianiÂ®14termsÂ¢Â¥play[Xbox,aroundSeeshallfromTheseÂ¥2,500,000,000lifeFreefamily|<_Qhim13Price:musicmoresuitcase?...CanadianThephotos:ZYjZ`@be>Â£saidcannot"Â§iÂ¢~setNorthpeopleabledatamoneyJobshadhomeÂ£5K-10...+50Â°C,sincemight@â€˜+YourOBack1,@=i.donâ€˜t.understand.?days&hbar;:similarGuildford~,Oxford/zÃ©roSouth}{amCheckGardenMessagesomethingposted{>systemGreatperx-74.7367Â°,by:Visitan)Blogmeâ€œ%productRate[INTL:it]Howtao..hihi!!gosh..ngathatagainstbeforeour=anti-inflationar%8providedâ‚¬*doMarÂ¢%rYVzÃ©duringarticlesStockpersonalDepartment23PostÂ®Â©Â°Â°#!OrdercomputerFAQPrivacyâ‚¬â€œShippingresearchÂ©gameCJ.CopyrightwhatNovemberthose2005*&LyricsAccountFoodâ€™=eBaytype4RSSCommentsmaingetCurrentStreet\=PAboutshould));memberRe:ListReserved.(2)`{if...oa..oa..oa..:"){>â‚¬*Officemeansj;AprilMovies2003faith-buffy**places=0,1,2,...,t-1}thatArticlestheyworkingzÃ©|&Â¢Â¥Center5WeathercannumberOpeninitial_transition))havingAMAQueo!Store"Â§contactLearn17Business))]ReviewsAccessoriesworkstartPublic"Esioff-LÃ©onGuideprices~oqtopGroupYahoo!MJournalâ€™=resultswithInfoOFY?ScienceAugustpicturesneedAdvancedopenPages$14.00/19.50(Canada)OverallTheywhyAmerican1.Â®?2areshowschoolcreditused22MoreleastResearchto'+MostMapâ‚¬=changeÂ¢~&Sale``safety-significantSt.milesDayTools]`Â®Â©Â¥%highIFondation-SolidaritÃ©Mr.theLinkâ€˜Râ€™ownItemÂ°Â°which154-169|56-70|28-41FebruaryMy10h$@CountyAirâ€œanti-authoritarianâ€reallypageEnglishCartDatacomeaboutus25until|<timeshebackAddForLinksFindclickElectronicsthisViewBoardimportantProfileDate:.BlackYouRightsForumsgrouppoweritemssexrequiredJanuary%METATITLE%sayproductsavailablewaterdoxal-5Â¢-phosphate.Mediaâ€˜+JanBookPacific\Afghanistantext(1)TSendUK7Replysendformsincefirstintention-in-action;betweenPad,Standard,14X27EagoingQâ€.~#into~#5Â¢-TGTAACCTCTACTCCCAtransnationalizationSolovelocalI'mbeingTOweb"""

langdata = '/home/william-manley/Projects/tesseract-ocr/training/langdata'

Font = namedtuple('Font', 'id name filename base flags')

class FontFlags(object):
    ITALIC = 1 << 0
    BOLD = 1 << 1
    FIXED = 1 << 2
    SERIF = 1 << 3
    FRAKTUR = 1 << 4

def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("font_file", nargs='+',
                        help="Filename of a OpenType font")
    parser.add_argument(
        "--lang", default="eng",
        help="Three letter ISO 639-2 language code.  e.g. \"eng\"")
    parser.add_argument("--exp", default=0, help="Not sure yet...")
    parser.add_argument("--shape-clustering", action="store_true",
                        help="Enable this option for Indic languages")
    args = parser.parse_args(argv[1:])

    fonts = []

    for font in args.font_file:
        family, style = ImageFont.truetype(font).getname()

        if style == 'Regular':
            name = family
        else:
            name = family + " " + style

        fid = "".join(name.split())
        flags = 0
        if "italic" in style.lower():
            flags |= FontFlags.ITALIC
        if "bold" in style.lower():
            flags |= FontFlags.BOLD
        #TODO: Work out if it's fixed width or has serifs
        fonts.append(Font(id=fid,
                          name=name,
                          filename=os.path.abspath(font),
                          base='%s.%s.exp%i' % (args.lang, fid, args.exp),
                          flags=flags))
        

    outfile = os.path.abspath("%s.traineddata" % args.lang)

    tmpdir = tempfile.mkdtemp()
    try:
        os.chdir(tmpdir)
        for font in fonts:
            # Generate box files
            with NamedTemporaryFile() as text:
                text.write(example_text.encode('utf-8'))
                text.flush()
                subprocess.check_call([
                    'text2image',
                    '--text=%s' % text.name,
                    '--outputbase=%s' % font.base,
                    '--font=%s' % font.name,
                    '--fonts_dir=%s' % os.path.dirname(font.filename),
                    '--degrade_image=false',
                    '--xsize=1280',
                    '--ysize=720',
                    '--ptsize=6'
                    ])

            subprocess.check_call([
                'tesseract',
                '%s.tif' % font.base,
                font.base,
                'box.train.stderr'])

        subprocess.check_call(
            ['unicharset_extractor'] +
            ['%s.box' % font.base for font in fonts])

        subprocess.check_call([
            'set_unicharset_properties',
            '-U', 'unicharset', '-O', 'unicharset', '--script_dir=%s' % langdata])

        with open('font_properties', 'w') as f:
            for font in fonts:
                f.write("%s %i %i %i %i %i\n" % (
                    font.id,
                    font.flags & FontFlags.ITALIC and 1,
                    font.flags & FontFlags.BOLD and 1,
                    font.flags & FontFlags.FIXED and 1,
                    font.flags & FontFlags.SERIF and 1,
                    font.flags & FontFlags.FRAKTUR and 1))

        if args.shape_clustering:
            subprocess.check_call([
                'shapeclustering',
                '-F', 'font_properties',
                '-U', 'unicharset'] +
                ['%s.tr' % f.base for f in fonts])

        subprocess.check_call([
            'mftraining',
            '-F', 'font_properties',
            '-U', 'unicharset',
            '-O', '%s.unicharset' % args.lang] +
            ['%s.tr' % f.base for f in fonts])
        assert os.path.exists('%s.unicharset' % args.lang)

        subprocess.check_call(['cntraining'] + ['%s.tr' % f.base for f in fonts])

        os.rename('inttemp', '%s.inttemp' % args.lang)
        os.rename('pffmtable', '%s.pffmtable' % args.lang)
        os.rename('shapetable', '%s.shapetable' % args.lang)
        os.rename('font_properties', '%s.font_properties' % args.lang)
        os.rename('normproto', '%s.normproto' % args.lang)

        subprocess.check_call(['combine_tessdata', '%s.' % args.lang])
        os.rename('%s.traineddata' % args.lang, outfile)
    finally:
        print tmpdir
#        rmtree(tmpdir)

if __name__ == '__main__':
    sys.exit(main(sys.argv))
